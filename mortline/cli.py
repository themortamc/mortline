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

from . import animado, clips, escenas, guion, musica, publicacion, subtitulos, video, voz
from .config import Config, cargar
from .historial import Historial


def _slug(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:48] or "reel"


def nombre_archivo(datos: dict) -> str:
    """Nombre del video = su título (el de la caja de arriba), apto para cualquier sistema."""
    titulo = (datos.get("titulo") or datos.get("tema") or "reel").strip()
    titulo = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", titulo)
    titulo = titulo.replace("¿", "").replace("¡", "")
    titulo = re.sub(r"\s+", " ", titulo).strip(" .")
    return titulo[:80] or "reel"


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
               voz_nombre: str | None, con_musica: bool, producto: str | None = None,
               estilo: str = "animado") -> Path:
    t0 = time.time()
    _paso(1, "Escribiendo el guion con FreeLLMAPI…")
    datos = guion.escribir(cfg, hist, tema=tema, rubro=rubro, producto=producto, estilo=estilo)
    print(f"   Tema: {datos['tema']}\n   Gancho: {datos['gancho']}\n   Llamado: {datos['cta']}")

    carpeta = cfg.salida / f"{datetime.now():%Y-%m-%d_%H%M}_{_slug(datos['tema'])}"
    try:
        return _armar(cfg, hist, datos, carpeta, voz_nombre, con_musica, producto, t0, estilo=estilo)
    except BaseException:
        shutil.rmtree(carpeta, ignore_errors=True)  # no dejar reels a medio hacer
        raise


def _armar(cfg, hist, datos, carpeta, voz_nombre, con_musica, producto, t0, rehacer=False,
           estilo="animado") -> Path:
    trabajo = carpeta / ".trabajo"
    trabajo.mkdir(parents=True, exist_ok=True)
    (carpeta / "guion.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    audio = carpeta / "voz.wav"
    if rehacer and audio.exists():
        _paso(2, "Reutilizo la voz que ya estaba grabada…")
    else:
        _paso(2, f"Grabando la voz con GGNarrator ({voz_nombre or cfg.voz})…")
        crudo = trabajo / "voz_cruda.wav"
        voz.generar(cfg, guion.texto_locucion(datos), crudo, voz_nombre)
        _recortar_silencio(crudo, audio)
    dur_voz = video.duracion(audio)
    print(f"   {dur_voz:.1f} s de locución")

    _paso(3, "Sincronizando subtítulos palabra por palabra (Whisper)…")
    textos = [e["texto"] for e in datos["escenas"]]
    palabras = subtitulos.alinear(cfg, audio, textos)
    tramos = subtitulos.tramos_escenas(palabras, len(textos), dur_voz)

    if estilo == "animado":
        _paso(4, "Diseñando las escenas animadas con FreeLLMAPI…")
        if rehacer and datos.get("visuales"):
            visuales, origen = datos["visuales"], "guardadas"
            tr_vis = escenas.tiempos(visuales, palabras, dur_voz)
        else:
            visuales, tr_vis, origen = escenas.generar(cfg, datos, palabras, dur_voz)
        datos["visuales"] = visuales
        (carpeta / "guion.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   {len(visuales)} escenas ({origen}): " + ", ".join(v["plantilla"] for v in visuales))
        materiales, creditos = [], []
    else:
        _paso(4, f"Buscando clips libres en {clips.proveedor(cfg)}…")
        usados = hist.clips_usados()
        materiales, creditos = [], []
        caps = clips.capturas(cfg, producto, trabajo / "capturas") if producto else []
        n_cap = 0
        for (ini, fin), escena in zip(tramos, datos["escenas"]):
            n = video.tomas_por_escena(fin - ini)
            if escena["buscar"].strip().upper() == "CAPTURA" and caps:
                mats = [caps[(n_cap + j) % len(caps)] for j in range(min(n, len(caps)))]
                n_cap += 1
                materiales.append(mats)
                creditos += [m.credito for m in mats]
                print(f"   «captura de la planilla»: {len(mats)} imagen(es)")
                continue
            if escena["buscar"].strip().upper() == "CAPTURA":
                escena["buscar"] = "small business owner laptop"
            mats = clips.buscar(cfg, escena["buscar"], n, (fin - ini) / n + 1, usados, trabajo / "clips")
            if not mats:
                mats = clips.buscar(cfg, "small business shop", n, 3, usados, trabajo / "clips")
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
    inicio_placa = video.cuando_placa(tramos, dur_voz)
    ass = trabajo / "subtitulos.ass"
    reel = carpeta / f"{nombre_archivo(datos)}.mp4"
    for viejo in carpeta.glob("*.mp4"):  # al rehacer, no dejar el video anterior con otro nombre
        if viejo != reel:
            viejo.unlink()
    if estilo == "animado":
        subtitulos.escribir_ass(palabras, ass, hasta=inicio_placa, titulo="")
        total = dur_voz + video.COLA
        lista = []
        for v, (ini, fin) in zip(visuales, tr_vis):
            if lista and ini >= inicio_placa - 0.4:
                break  # la placa final tapa lo que queda
            lista.append({**v, "ini": ini, "fin": fin})
        lista[-1]["fin"] = inicio_placa
        placa = {"ini": inicio_placa, "llamado": guion.CTAS[datos["cta"]]["placa"], "web": cfg.web,
                 "precio": _precio_txt(cfg, producto)}
        t_r = time.time()
        mudo = trabajo / "mudo.mp4"
        desb = animado.renderizar(lista, placa, total, cfg.assets, trabajo, mudo,
                                  cuadro_portada=(-0.5, trabajo / "portada_fondo.jpg"))
        print(f"   Render de {total * animado.FPS:.0f} cuadros en {time.time() - t_r:.0f} s")
        for d in desb[:6]:
            print(f"   ⚠ posible desborde: {d}")
        total = video.mezclar(mudo=mudo, voz=audio, ass=ass, musica=tema_musical, assets=cfg.assets,
                              trabajo=trabajo, salida=reel, total=total)
    else:
        subtitulos.escribir_ass(palabras, ass, hasta=inicio_placa, titulo=datos.get("titulo", ""))
        total = video.armar(
            tramos=tramos, materiales=materiales, voz=audio, dur_voz=dur_voz, ass=ass,
            musica=tema_musical, assets=cfg.assets, llamado=guion.CTAS[datos['cta']]['placa'], web=cfg.web,
            precio=_precio_txt(cfg, producto),
            trabajo=trabajo, salida=reel,
        )

    _paso(6, "Guardando caption, créditos e historial…")
    (carpeta / "caption.txt").write_text(publicacion.caption(cfg, datos, producto), encoding="utf-8")
    fondo = trabajo / "portada_fondo.jpg"
    publicacion.portada(cfg, datos, materiales, carpeta / "portada.jpg", trabajo,
                        fondo=fondo if estilo == "animado" and fondo.exists() else None)
    if tema_musical:
        creditos.append(f"Música: {tema_musical.name}")
    (carpeta / "creditos.txt").write_text("\n".join(dict.fromkeys(creditos)) + "\n", encoding="utf-8")
    shutil.rmtree(trabajo, ignore_errors=True)
    if rehacer:
        print(f"\n✅ Rehecho en {time.time() - t0:.0f} s\n   {reel}")
        return reel
    hist.agregar({
        "combo": datos.get("combo"), "tema": datos["tema"], "gancho": datos["gancho"],
        "titulo": datos.get("titulo", ""), "cta": datos["cta"], "voz": voz_nombre or cfg.voz,
        "clips": sorted({m.id for ms in materiales for m in ms}), "duracion": total, "estilo": estilo,
        "carpeta": str(carpeta),
    })
    _guardar_en_github()
    print(f"\n✅ Listo en {time.time() - t0:.0f} s · {total:.1f} s de reel\n   {reel}\n   Caption: {carpeta / 'caption.txt'}")
    return reel


def _precio_txt(cfg, producto) -> str:
    if not producto:
        return ""
    p = guion.datos_producto(cfg, producto)
    return ("$" + f"{p['precio']:,}".replace(",", ".") + " · pago único") if p.get("precio") else ""


def _guardar_en_github() -> None:
    """Sube el historial al repo para que no se pierda (si falla, sigue sin cortar el reel)."""
    from .config import ROOT

    git = ["git", "-C", str(ROOT)]
    try:
        subprocess.run([*git, "add", "data/historial.json"], check=True, capture_output=True, timeout=30)
        hay = subprocess.run([*git, "diff", "--cached", "--quiet"], capture_output=True, timeout=30)
        if hay.returncode == 0:
            return
        subprocess.run([*git, "commit", "-m", "historial: nuevo reel"], check=True, capture_output=True, timeout=30)
        subprocess.run([*git, "push", "-q"], check=True, capture_output=True, timeout=90)
        print("   Historial guardado en GitHub.")
    except (subprocess.SubprocessError, OSError):
        print("   (No pude subir el historial a GitHub; queda guardado en el repo local.)")


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
    ap.add_argument("--estilo", choices=["animado", "stock"], default="animado",
                    help="animado: motion graphics propios (por defecto); stock: clips de bancos libres")
    ap.add_argument("--rehacer", help="carpeta de un reel ya hecho: rehace imágenes y video con la misma voz y guion")
    ap.add_argument("--producto", help="reel de un producto digital de la tienda (slug, ej: calculadora-de-precios)")
    args = ap.parse_args(argv)

    cfg = cargar()
    hist = Historial(cfg.datos)
    if args.rehacer:
        carpeta = Path(args.rehacer).expanduser().resolve()
        datos = json.loads((carpeta / "guion.json").read_text(encoding="utf-8"))
        datos.setdefault("cta", "whatsapp")
        datos.setdefault("gancho", datos["escenas"][0]["texto"])
        producto = (datos.get("combo") or "").removeprefix("producto/") if str(datos.get("combo", "")).startswith("producto/") else None
        _armar(cfg, hist, datos, carpeta, args.voz, not args.sin_musica, producto, time.time(), rehacer=True, estilo=args.estilo)
        return 0
    if args.tema == "historial":
        _historial(hist)
        return 0
    errores = 0
    for i in range(args.cantidad):
        if args.cantidad > 1:
            print(f"\n━━━ Reel {i + 1} de {args.cantidad} ━━━")
        try:
            hacer_reel(cfg, hist, args.tema, args.rubro, args.voz, not args.sin_musica, args.producto, args.estilo)
        except Exception as exc:  # seguir con el próximo si se hace una tanda
            errores += 1
            print(f"\n❌ {exc}", file=sys.stderr)
            if args.cantidad == 1:
                return 1
    return 1 if errores == args.cantidad else 0


if __name__ == "__main__":
    raise SystemExit(main())
