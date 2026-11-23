"""Armado con ffmpeg: clips cortados al ritmo de la voz, placa final, música y subtítulos."""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

from .clips import Material

W, H, FPS = 1080, 1920, 30
COLA = 1.0          # segundos de placa después de la voz: placa total ~2 s (una placa quieta larga hace swipear)
TOMA = 2.4          # duración ideal de cada toma: cambiar de imagen antes de 3 s retiene más
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]


class VideoError(RuntimeError):
    pass


def _ff(args: list[str], limite: int = 600) -> None:
    """Corre ffmpeg con tiempo máximo: si se traba, corta y avisa en vez de colgarse."""
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin", *args],
                           capture_output=True, text=True, timeout=limite)
    except subprocess.TimeoutExpired:
        raise VideoError(f"ffmpeg tardó más de {limite} s y se cortó (paso: {args[-1]}).")
    if r.returncode != 0:
        raise VideoError(r.stderr.strip()[-1500:])


def duracion(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def tomas_por_escena(seg: float) -> int:
    return max(1, round(seg / TOMA))


ZOOM = 0.07         # zoom lento en cada toma: un poco de movimiento retiene más que una imagen quieta


def _movimiento(frames: int, n: int) -> str:
    """Zoom suave que alterna entre acercar y alejar (se ve hecho a mano, no repetitivo)."""
    z = f"1+{ZOOM}*on/{frames}" if n % 2 == 0 else f"{1 + ZOOM}-{ZOOM}*on/{frames}"
    return (f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={W}x{H}:fps={FPS}")


def _toma(m: Material, inicio: float, dur: float, destino: Path, n: int = 0) -> None:
    frames = max(int(dur * FPS), 1)
    if m.estilo == "captura":
        # Planilla real: alta 720 px (legible en el celular), sobre fondo de marca. Si es más ancha
        # que la pantalla, paneo lento de izquierda a derecha para recorrerla.
        # Lo más grande posible (que se lea en el celular), pero si es ancha el paneo no puede pasar
        # de ~350 px/s: más rápido no se alcanza a leer.
        from PIL import Image

        ancho0, alto0 = Image.open(m.path).size
        # Planillas muy anchas y bajas: se muestran las columnas de la izquierda (las importantes)
        # bien grandes, en vez de achicar todo o recorrerla a toda velocidad.
        recorte = f"crop={min(ancho0, int(alto0 * 2.4))}:{alto0}:0:0," if ancho0 / alto0 > 2.4 else ""
        ancho1 = min(ancho0, int(alto0 * 2.4)) if recorte else ancho0
        if alto0 * 1040 / ancho1 >= 420:
            escala = min(800 / alto0, 1040 / ancho1)  # entra entera y quieta, a todo el ancho
        else:
            escala = min(800 / alto0, (1040 + 350 * dur) / ancho1, 420 / alto0)  # ancha: paneo lento
        alto = int(alto0 * escala) // 2 * 2
        y = 340 + (800 - alto) // 2
        filtro = (f"[1:v]{recorte}scale=-2:{alto},setsar=1[s];"
                  f"[0:v][s]overlay=x='if(gt(overlay_w,1040),20-(overlay_w-1040)*t/{dur:.3f},(main_w-overlay_w)/2)'"
                  f":y={y}:eval=frame,fps={FPS},format=yuv420p[v]")
        _ff(["-f", "lavfi", "-i", f"color=c=0x140B24:s={W}x{H}:d={dur:.3f}:r={FPS}", "-loop", "1", "-t", f"{dur:.3f}",
             "-i", str(m.path), "-filter_complex", filtro, "-map", "[v]", "-frames:v", str(frames), *X264, str(destino)])
        return
    if m.es_video:
        total = duracion(m.path)
        loop = ["-stream_loop", "-1"] if total < inicio + dur else []
        # Se agranda al doble antes del zoom para que el movimiento no "tiemble".
        vf = (f"fps={FPS},scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
              f"{_movimiento(frames, n)},setsar=1,eq=saturation=1.06")
        _ff([*loop, "-ss", f"{inicio:.2f}", "-t", f"{dur:.3f}", "-i", str(m.path),
             "-vf", vf, "-an", "-frames:v", str(frames), *X264, str(destino)])
    else:
        frames = max(int(dur * FPS), 1)
        # Ken Burns suave para fotos: zoom lento hacia el centro.
        vf = (f"scale={int(W*1.2)}:{int(H*1.2)}:force_original_aspect_ratio=increase,"
              f"crop={int(W*1.2)}:{int(H*1.2)},"
              f"zoompan=z='1+0.10*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
              f"d={frames}:s={W}x{H}:fps={FPS},setsar=1")
        _ff(["-loop", "1", "-i", str(m.path), "-t", f"{dur:.3f}", "-vf", vf, "-an", *X264, str(destino)])


def cuando_placa(tramos, dur_voz: float) -> float:
    """La placa entra en el último segundo de la voz (no al principio del llamado)."""
    return max(tramos[-1][0] + 0.6, dur_voz - 1.1)


def _placa(assets: Path, dur: float, llamado: str, web: str, trabajo: Path, destino: Path, precio: str = "") -> None:
    """Placa final: fondo liso de marca, logo recortado, llamado en botón y web en blanco grande.
    Todo entra escalonado (logo, botón, web, aviso) dentro de la zona segura de Instagram/TikTok."""
    logo = assets / "logo.jpg"
    fuerte = assets / "fonts" / "HankenGrotesk-ExtraBold.ttf"
    media = assets / "fonts" / "HankenGrotesk-SemiBold.ttf"
    textos = {"t1.txt": llamado, "t2.txt": web, "t3.txt": "Link en el perfil", "t4.txt": precio or " "}
    for nombre, t in textos.items():
        (trabajo / nombre).write_text(t, encoding="utf-8")

    def entra(desde: float, dur_: float = 0.3) -> str:
        return f"if(lt(t,{desde}),0,min(1,(t-{desde})/{dur_}))"

    def sube(y: int, desde: float, px: int = 28) -> str:
        return f"{y}+{px}*(1-min(1,max(0,(t-{desde})/0.3)))"

    bw, bh, br = 820, 136, 68
    redondo = f"255*lte(hypot(max(0,abs(X-W/2)-(W/2-{br})),max(0,abs(Y-H/2)-(H/2-{br}))),{br})"
    filtro = (
        f"color=c=0x0E0A16:s={W}x{H}:d={dur:.3f}:r={FPS}[fondo];"
        f"[0:v]format=rgba,colorkey=0x000000:0.22:0.08,scale=640:640,fade=t=in:st=0:d=0.3:alpha=1[logo];"
        f"color=c=white:s={bw}x{bh}:d={dur:.3f}:r={FPS},format=rgba,geq=r=255:g=255:b=255:a='{redondo}',"
        f"fade=t=in:st=0.25:d=0.3:alpha=1[boton];"
        f"[fondo][logo]overlay=x=(W-w)/2:y='{sube(330, 0)}':eval=frame[a];"
        f"[a][boton]overlay=x=(W-w)/2:y='{sube(1080, 0.25)}':eval=frame,"
        f"drawtext=fontfile='{media}':textfile='{trabajo / 't1.txt'}':fontcolor=0x17141F:fontsize=52:"
        f"x=(w-tw)/2:y='{sube(1080, 0.25)}+({bh}-th)/2':alpha='{entra(0.25)}',"
        f"drawtext=fontfile='{fuerte}':textfile='{trabajo / 't2.txt'}':fontcolor=white:fontsize=96:"
        f"x=(w-tw)/2:y='{sube(1290, 0.4)}':alpha='{entra(0.4)}',"
        f"drawtext=fontfile='{media}':textfile='{trabajo / 't3.txt'}':fontcolor=0xB9A8D9:fontsize=46:"
        f"x=(w-tw)/2:y='{sube(1420, 0.55)}':alpha='{entra(0.55)}',"
        + (f"drawtext=fontfile='{fuerte}':textfile='{trabajo / 't4.txt'}':fontcolor=0xC9A6FF:fontsize=58:"
           f"x=(w-tw)/2:y='{sube(960, 0.15)}':alpha='{entra(0.15)}'," if precio else "")
        + f"fps={FPS},setsar=1,format=yuv420p[v]"
    )
    _ff(["-loop", "1", "-t", f"{dur:.3f}", "-i", str(logo), "-filter_complex", filtro, "-map", "[v]",
         "-t", f"{dur:.3f}", *X264, str(destino)])


def armar(*, tramos: list[tuple[float, float]], materiales: list[list[Material]], voz: Path,
          dur_voz: float, ass: Path, musica: Path | None, assets: Path, llamado: str, web: str, precio: str = "",
          trabajo: Path, salida: Path) -> float:
    """Devuelve la duración final. `tramos[-1]` es la escena del llamado: ahí entra la placa."""
    if not shutil.which("ffmpeg"):
        raise VideoError("No encuentro ffmpeg instalado.")
    trabajo.mkdir(parents=True, exist_ok=True)
    inicio_placa = cuando_placa(tramos, dur_voz)
    total = dur_voz + COLA

    partes: list[Path] = []
    n = 0
    for (ini, fin), mats in zip(tramos, materiales):
        fin = min(fin, inicio_placa)
        if fin - ini < 0.2:
            continue
        k = tomas_por_escena(fin - ini)
        paso = (fin - ini) / k
        for j in range(k):
            m = mats[j % len(mats)]
            # Si se repite el mismo clip dentro de la escena, usar otro tramo del video.
            offset = (j // len(mats)) * 4.0 + 0.3
            destino = trabajo / f"toma_{n:03d}.mp4"
            _toma(m, offset, paso, destino, n)
            partes.append(destino)
            n += 1
    placa = trabajo / "placa.mp4"
    _placa(assets, total - inicio_placa, llamado, web, trabajo, placa, precio)
    partes.append(placa)

    lista = trabajo / "lista.txt"
    lista.write_text("".join(f"file '{p}'\n" for p in partes), encoding="utf-8")
    mudo = trabajo / "mudo.mp4"
    _ff(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(mudo)])

    mezclar(mudo=mudo, voz=voz, ass=ass, musica=musica, assets=assets, trabajo=trabajo, salida=salida, total=total)
    return math.floor(total * 100) / 100


def mezclar(*, mudo: Path, voz: Path, ass: Path, musica: Path | None, assets: Path, trabajo: Path,
            salida: Path, total: float) -> float:
    """Video mudo + subtítulos quemados + voz y música (-14 LUFS). Sirve para el estilo stock y el animado."""
    fonts = assets / "fonts"
    vf = f"ass='{ass}':fontsdir='{fonts}'"
    # 1) Audio aparte y con duración fija: la música en bucle se corta en la ENTRADA (-t),
    #    así ningún stream queda infinito (antes eso podía colgar a ffmpeg).
    mezcla = trabajo / "mezcla.wav"
    voz_f = f"[0:a]aresample=48000,apad=whole_dur={total:.3f}[voz]"
    if musica:
        _ff(["-i", str(voz), "-stream_loop", "-1", "-t", f"{total:.3f}", "-i", str(musica),
             "-filter_complex",
             f"{voz_f};[1:a]aresample=48000,volume=0.13,afade=t=in:st=0:d=0.6,"
             f"afade=t=out:st={total-1.6:.3f}:d=1.6[mus];"
             f"[voz][mus]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
             "-map", "[a]", "-ar", "48000", str(mezcla)], limite=180)
    else:
        _ff(["-i", str(voz), "-filter_complex", f"{voz_f};[voz]loudnorm=I=-14:TP=-1.5:LRA=11[a]",
             "-map", "[a]", "-ar", "48000", str(mezcla)], limite=180)

    # 2) Video final: subtítulos quemados + la mezcla.
    _ff(["-i", str(mudo), "-i", str(mezcla), "-vf", vf, "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
         "-movflags", "+faststart", str(salida)])
    return math.floor(total * 100) / 100
