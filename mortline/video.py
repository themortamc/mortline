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


def _ff(args: list[str]) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
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


def _toma(m: Material, inicio: float, dur: float, destino: Path) -> None:
    cubrir = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    if m.es_video:
        total = duracion(m.path)
        loop = ["-stream_loop", "-1"] if total < inicio + dur else []
        _ff([*loop, "-ss", f"{inicio:.2f}", "-t", f"{dur:.3f}", "-i", str(m.path),
             "-vf", f"{cubrir},fps={FPS},eq=saturation=1.06", "-an", *X264, str(destino)])
    else:
        frames = max(int(dur * FPS), 1)
        # Ken Burns suave para fotos: zoom lento hacia el centro.
        vf = (f"scale={int(W*1.2)}:{int(H*1.2)}:force_original_aspect_ratio=increase,"
              f"crop={int(W*1.2)}:{int(H*1.2)},"
              f"zoompan=z='1+0.10*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
              f"d={frames}:s={W}x{H}:fps={FPS},setsar=1")
        _ff(["-loop", "1", "-i", str(m.path), "-t", f"{dur:.3f}", "-vf", vf, "-an", *X264, str(destino)])


def _placa(assets: Path, dur: float, whatsapp: str, web: str, trabajo: Path, destino: Path) -> None:
    logo = assets / "logo.jpg"
    fuerte = assets / "fonts" / "HankenGrotesk-ExtraBold.ttf"
    media = assets / "fonts" / "HankenGrotesk-SemiBold.ttf"
    textos = {"t1.txt": "Escribime por WhatsApp", "t2.txt": whatsapp, "t3.txt": web}
    for nombre, t in textos.items():
        (trabajo / nombre).write_text(t, encoding="utf-8")
    fade = f"fade=t=in:st=0:d=0.35"
    filtro = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.08[fondo];"
        f"[1:v]scale=860:860[logo];"
        f"[fondo][logo]overlay=(W-w)/2:330,"
        f"drawtext=fontfile='{media}':textfile='{trabajo/'t1.txt'}':fontcolor=white:fontsize=64:x=(w-tw)/2:y=1260,"
        f"drawtext=fontfile='{fuerte}':textfile='{trabajo/'t2.txt'}':fontcolor=0x8B2CFF:fontsize=86:x=(w-tw)/2:y=1360:"
        f"borderw=3:bordercolor=white@0.0,"
        f"drawtext=fontfile='{media}':textfile='{trabajo/'t3.txt'}':fontcolor=white@0.85:fontsize=52:x=(w-tw)/2:y=1500,"
        f"fps={FPS},setsar=1,{fade}[v]"
    )
    _ff(["-loop", "1", "-t", f"{dur:.3f}", "-i", str(logo), "-loop", "1", "-t", f"{dur:.3f}", "-i", str(logo),
         "-filter_complex", filtro, "-map", "[v]", *X264, str(destino)])


def armar(*, tramos: list[tuple[float, float]], materiales: list[list[Material]], voz: Path,
          dur_voz: float, ass: Path, musica: Path | None, assets: Path, whatsapp: str, web: str,
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
            _toma(m, offset, paso, destino)
            partes.append(destino)
            n += 1
    placa = trabajo / "placa.mp4"
    _placa(assets, total - inicio_placa, whatsapp, web, trabajo, placa)
    partes.append(placa)

    lista = trabajo / "lista.txt"
    lista.write_text("".join(f"file '{p}'\n" for p in partes), encoding="utf-8")
    mudo = trabajo / "mudo.mp4"
    _ff(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(mudo)])

    fonts = assets / "fonts"
    vf = f"ass='{ass}':fontsdir='{fonts}'"
    entradas = ["-i", str(mudo), "-i", str(voz)]
    if musica:
        entradas += ["-stream_loop", "-1", "-i", str(musica)]
        audio = (
            f"[1:a]aresample=48000,apad,atrim=0:{total:.3f}[voz];"
            f"[2:a]aresample=48000,atrim=0:{total:.3f},volume=0.13,"
            f"afade=t=in:st=0:d=0.6,afade=t=out:st={total-1.6:.3f}:d=1.6[mus];"
            f"[voz][mus]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
        )
    else:
        audio = f"[1:a]aresample=48000,apad,atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    _ff([*entradas, "-filter_complex", f"[0:v]{vf}[v];{audio}", "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
         "-movflags", "+faststart", str(salida)])
    return math.floor(total * 100) / 100
