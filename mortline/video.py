"""Armado con ffmpeg: clips cortados al ritmo de la voz, placa final, música y subtítulos."""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

from .clips import Material

W, H, FPS = 1080, 1920, 30
COLA = 1.3          # segundos de placa final después de que termina la voz (corta: cuenta para la retención)
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
        alto, y = 720, 400
        filtro = (f"[1:v]scale=-2:{alto},setsar=1[s];"
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


def _placa(assets: Path, dur: float, llamado: str, web: str, trabajo: Path, destino: Path) -> None:
    """Placa final: logo, la web bien grande y el llamado de este reel (sin teléfono)."""
    logo = assets / "logo.jpg"
    fuerte = assets / "fonts" / "HankenGrotesk-ExtraBold.ttf"
    media = assets / "fonts" / "HankenGrotesk-SemiBold.ttf"
    textos = {"t1.txt": llamado, "t2.txt": web, "t3.txt": "Link en el perfil"}
    for nombre, t in textos.items():
        (trabajo / nombre).write_text(t, encoding="utf-8")
    fade = f"fade=t=in:st=0:d=0.35"
    filtro = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.08[fondo];"
        f"[1:v]scale=860:860[logo];"
        f"[fondo][logo]overlay=(W-w)/2:330,"
        f"drawtext=fontfile='{media}':textfile='{trabajo/'t1.txt'}':fontcolor=white:fontsize=64:x=(w-tw)/2:y=1260,"
        f"drawtext=fontfile='{fuerte}':textfile='{trabajo/'t2.txt'}':fontcolor=0x8B2CFF:fontsize=96:x=(w-tw)/2:y=1355,"
        f"drawtext=fontfile='{media}':textfile='{trabajo/'t3.txt'}':fontcolor=white@0.85:fontsize=52:x=(w-tw)/2:y=1500,"
        f"fps={FPS},setsar=1,{fade}[v]"
    )
    _ff(["-loop", "1", "-t", f"{dur:.3f}", "-i", str(logo), "-loop", "1", "-t", f"{dur:.3f}", "-i", str(logo),
         "-filter_complex", filtro, "-map", "[v]", *X264, str(destino)])


def armar(*, tramos: list[tuple[float, float]], materiales: list[list[Material]], voz: Path,
          dur_voz: float, ass: Path, musica: Path | None, assets: Path, llamado: str, web: str,
          trabajo: Path, salida: Path) -> float:
    """Devuelve la duración final. `tramos[-1]` es la escena del llamado: ahí entra la placa."""
    if not shutil.which("ffmpeg"):
        raise VideoError("No encuentro ffmpeg instalado.")
    trabajo.mkdir(parents=True, exist_ok=True)
    inicio_placa = max(tramos[-1][0], dur_voz - 2.8)
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
    _placa(assets, total - inicio_placa, llamado, web, trabajo, placa)
    partes.append(placa)

    lista = trabajo / "lista.txt"
    lista.write_text("".join(f"file '{p}'\n" for p in partes), encoding="utf-8")
    mudo = trabajo / "mudo.mp4"
    _ff(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(mudo)])

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
