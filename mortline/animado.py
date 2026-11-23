"""Render de escenas animadas: plantillas HTML/CSS/JS pintadas cuadro a cuadro con Chromium headless.

El tiempo lo controla Python (frame(t) en la página), no corre en tiempo real: el resultado es
determinista y no depende de la velocidad de la máquina. Los cuadros van a ffmpeg por una tubería.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

W, H, FPS = 1080, 1920, 30
AQUI = Path(__file__).resolve().parent / "animado"


class RenderError(RuntimeError):
    pass


def iconos_disponibles() -> list[str]:
    return sorted(p.stem for p in (AQUI / "iconos").glob("*.svg"))


def _iconos() -> dict[str, str]:
    """Contenido interno de cada SVG de Lucide (los trazos), para incrustarlo en la página."""
    out = {}
    for p in (AQUI / "iconos").glob("*.svg"):
        m = re.search(r"<svg[^>]*>(.*)</svg>", p.read_text(encoding="utf-8"), re.S)
        if m:
            out[p.stem] = m.group(1).strip()
    return out


def _pagina(assets: Path, trabajo: Path) -> Path:
    from .temas import FUENTES

    fuentes = {fam: (assets / "fonts" / arch).as_uri() for fam, arch in FUENTES.items()}
    media = (assets / "fonts" / "HankenGrotesk-SemiBold.ttf").as_uri()
    html = (AQUI / "escena.html").read_text(encoding="utf-8").replace("LOGO", (assets / "logo.jpg").as_uri())
    faces = "".join(f'@font-face{{font-family:"{f}";src:url("{u}")}}' for f, u in fuentes.items() if f != "HankenX")
    faces += (f'@font-face{{font-family:"HankenX";font-weight:800;src:url("{fuentes["HankenX"]}")}}'
              f'@font-face{{font-family:"HankenX";font-weight:600;src:url("{media}")}}')
    destino = trabajo / "escena.html"
    destino.write_text(html.replace("</head>", f"<style>{faces}</style></head>", 1), encoding="utf-8")
    return destino


def _tema(estilo: str) -> dict:
    from .temas import FUENTES, VISUAL

    v = dict(VISUAL[estilo])
    mov, esc = v.pop("mov"), v.pop("esc", 1)
    return {"nombre": estilo, "vars": v, "mov": mov, "esc": esc, "fuentes": sorted(FUENTES)}


def _abrir(p, assets: Path, trabajo: Path, escenas: list[dict], placa: dict, estilo: str):
    navegador = p.chromium.launch(args=["--disable-gpu", "--font-render-hinting=none"])
    pagina = navegador.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    pagina.goto(_pagina(assets, trabajo).as_uri())
    tema = _tema(estilo)
    pagina.evaluate("d => iniciar(d)", {"escenas": escenas, "placa": placa, "iconos": _iconos(), "tema": tema,
                                        "fuentes": {f: 1 for f in tema["fuentes"]}})
    pagina.evaluate("document.fonts.ready.then(() => 0)")
    return navegador, pagina


def renderizar(escenas: list[dict], placa: dict, total: float, assets: Path, trabajo: Path,
               destino: Path, estilo: str = "minimal", cuadro_portada: tuple[float, Path] | None = None) -> list:
    """Pinta `total` segundos a 30 fps y los codifica en `destino` (mudo). Devuelve desbordes detectados.

    escenas: [{plantilla, textos, icono, resaltar, ini, fin}] ; placa: {ini, llamado, web, precio}.
    """
    from playwright.sync_api import sync_playwright

    n = int(round(total * FPS))
    desbordes = []
    # Se revisa cada escena ya asentada (no durante la entrada, que se mueve desde afuera de la pantalla).
    revisar = {int((e["ini"] + min(2.0, 0.85 * (e["fin"] - e["ini"]))) * FPS) for e in escenas} | {int((placa["ini"] + 1.0) * FPS)}
    with sync_playwright() as p:
        navegador, pagina = _abrir(p, assets, trabajo, escenas, placa, estilo)
        ff = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin", "-f", "image2pipe",
             "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), str(destino)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i in range(n):
                t = i / FPS
                pagina.evaluate("t => frame(t)", t)
                if i in revisar:
                    desbordes += [(round(t, 2), *x) for x in pagina.evaluate("desbordes()")]
                ff.stdin.write(pagina.screenshot(type="jpeg", quality=95))
            if cuadro_portada:
                pagina.evaluate("t => frame(t)", cuadro_portada[0])
                pagina.screenshot(path=str(cuadro_portada[1]), type="jpeg", quality=92)
        finally:
            ff.stdin.close()
            rc = ff.wait()
            navegador.close()
        if rc != 0:
            raise RenderError(ff.stderr.read().decode()[-1200:])
    return desbordes


def cuadros(escenas: list[dict], placa: dict, tiempos: list[float], assets: Path, trabajo: Path,
            carpeta: Path, estilo: str = "minimal") -> list[Path]:
    """Guarda PNG de instantes concretos (para revisar el diseño a ojo)."""
    from playwright.sync_api import sync_playwright

    carpeta.mkdir(parents=True, exist_ok=True)
    out = []
    with sync_playwright() as p:
        navegador, pagina = _abrir(p, assets, trabajo, escenas, placa, estilo)
        for t in tiempos:
            pagina.evaluate("t => frame(t)", t)
            f = carpeta / f"t{t:05.2f}.png"
            pagina.screenshot(path=str(f))
            out.append(f)
        navegador.close()
    return out
