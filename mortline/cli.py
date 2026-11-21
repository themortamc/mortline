"""mortline: un comando, un reel.

    mortline                      elige solo un tema nuevo y hace el reel
    mortline "tema libre"         reel sobre ese tema
    mortline --rubro ferreterias  tema nuevo, pero de ese rubro
    mortline --cantidad 3         hace 3 reels seguidos (temas distintos)
    mortline historial            lista lo que ya se hizo
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from . import clips, guion, musica, subtitulos, video, voz
from .config import Config, cargar
from .historial import Historial


def _slug(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:48] or "reel"


def _paso(n: int, texto: str) -> None:
    print(f"\033[38;2;139;44;255m●\033[0m [{n}/6] {texto}", flush=True)


def _recortar_silencio(entrada: Path, salida: Path) -> None:
    """La voz tiene que arrancar en el cuadro 1: saca el silencio inicial."""
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(entrada), "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
         "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.25,areverse",
         str(salida)],
        check=True,
    )


def hacer_reel(cfg: Config, hist: Historial, tema: str | None, rubro: str | None,
               voz_nombre: str | None, con_musica: bool) -> Path:
    t0 = time.time()
    _paso(1, "Escribiendo el guion con FreeLLMAPI…")
    datos = guion.escribir(cfg, hist, tema=tema, rubro=rubro)
    print(f"   Tema: {datos['tema']}\n   Gancho: {datos['gancho']}")

    carpeta = cfg.salida / f"{datetime.now():%Y-%m-%d_%H%M}_{_slug(datos['tema'])}"
    trabajo = carpeta / ".trabajo"
    trabajo.mkdir(parents=True, exist_ok=True)
    (carpeta / "guion.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    _paso(2, f"Grabando la voz con GGNarrator ({voz_nombre or cfg.voz})…")
    crudo = trabajo / "voz_cruda.wav"
    voz.generar(cfg, guion.texto_locucion(datos), crudo, voz_nombre)
    audio = carpeta / "voz.wav"
    _recortar_silencio(crudo, audio)
    dur_voz = video.duracion(audio)
    print(f"   {dur_voz:.1f} s de locución")

    _paso(3, "Sincronizando subtítulos palabra por palabra (Whisper)…")
    textos = [e["texto"] for e in datos["escenas"]]
    palabras = subtitulos.alinear(cfg, audio, textos)
    tramos = subtitulos.tramos_escenas(palabras, len(textos), dur_voz)

    _paso(4, f"Buscando clips libres en {clips.proveedor(cfg)}…")
    usados = hist.clips_usados()
    materiales, creditos = [], []
    for (ini, fin), escena in zip(tramos, datos["escenas"]):
        n = video.tomas_por_escena(fin - ini)
        mats = clips.buscar(cfg, escena["buscar"], n, (fin - ini) / n + 1, usados, cfg.datos / "cache")
        if not mats:
            mats = clips.buscar(cfg, "small business shop", n, 3, usados, cfg.datos / "cache")
        if not mats and materiales:
            mats = materiales[-1]
        if not mats:
            raise RuntimeError(f"No encontré material para «{escena['buscar']}».")
        usados |= {m.id for m in mats}
        materiales.append(mats)
        creditos += [m.credito for m in mats]
        print(f"   «{escena['buscar']}»: {len(mats)} clip(s)")

    tema_musical = musica.elegir(cfg.musica) if con_musica else None

    _paso(5, "Armando el video (cortes, placa final, música, subtítulos)…")
    inicio_placa = max(tramos[-1][0], dur_voz - 2.8)
    ass = trabajo / "subtitulos.ass"
    subtitulos.escribir_ass(palabras, ass, hasta=inicio_placa, titulo=datos.get("titulo", ""))
    reel = carpeta / "reel.mp4"
    total = video.armar(
        tramos=tramos, materiales=materiales, voz=audio, dur_voz=dur_voz, ass=ass,
        musica=tema_musical, assets=cfg.assets, whatsapp=cfg.whatsapp, web=cfg.web,
        trabajo=trabajo, salida=reel,
    )

    _paso(6, "Guardando caption, créditos e historial…")
    caption = datos.get("caption", "").strip()
    tags = " ".join(datos.get("hashtags", []))
    (carpeta / "caption.txt").write_text(f"{caption}\n\n{tags}\n", encoding="utf-8")
    if tema_musical:
        creditos.append(f"Música: {tema_musical.name}")
    (carpeta / "creditos.txt").write_text("\n".join(dict.fromkeys(creditos)) + "\n", encoding="utf-8")
    shutil.rmtree(trabajo, ignore_errors=True)
    hist.agregar({
        "combo": datos.get("combo"), "tema": datos["tema"], "gancho": datos["gancho"],
        "titulo": datos.get("titulo", ""), "voz": voz_nombre or cfg.voz,
        "clips": sorted({m.id for ms in materiales for m in ms}), "duracion": total,
        "carpeta": str(carpeta),
    })
    print(f"\n✅ Listo en {time.time() - t0:.0f} s · {total:.1f} s de reel\n   {reel}\n   Caption: {carpeta / 'caption.txt'}")
    return reel


def _historial(hist: Historial) -> None:
    if not hist.reels:
        print("Todavía no hiciste ningún reel.")
        return
    for i, r in enumerate(hist.reels, 1):
        print(f"{i:3}. {r['fecha'][:16]}  {r.get('combo') or 'tema libre':38}  {r['gancho']}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mortline", description="Reels automáticos para mortups.")
    ap.add_argument("tema", nargs="?", help='tema libre, o "historial"')
    ap.add_argument("--rubro", choices=sorted(guion.RUBROS), help="elegir el rubro del reel")
    ap.add_argument("--voz", choices=["Puck", "Fenrir", "Charon", "Kore", "Zephyr"], help="voz de GGNarrator")
    ap.add_argument("--cantidad", type=int, default=1, help="cuántos reels hacer seguidos")
    ap.add_argument("--sin-musica", action="store_true", help="sin música de fondo")
    args = ap.parse_args(argv)

    cfg = cargar()
    hist = Historial(cfg.datos)
    if args.tema == "historial":
        _historial(hist)
        return 0
    errores = 0
    for i in range(args.cantidad):
        if args.cantidad > 1:
            print(f"\n━━━ Reel {i + 1} de {args.cantidad} ━━━")
        try:
            hacer_reel(cfg, hist, args.tema, args.rubro, args.voz, not args.sin_musica)
        except Exception as exc:  # seguir con el próximo si se hace una tanda
            errores += 1
            print(f"\n❌ {exc}", file=sys.stderr)
            if args.cantidad == 1:
                return 1
    return 1 if errores == args.cantidad else 0


if __name__ == "__main__":
    raise SystemExit(main())
