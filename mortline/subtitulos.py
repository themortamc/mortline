"""Tiempos por palabra (Whisper) alineados al guion + subtítulos ASS estilo TikTok."""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import Config

VIOLETA = "&H00FF2C8B"  # #8B2CFF en formato ASS (&HAABBGGRR)
BLANCO = "&H00FFFFFF"
NEGRO = "&H00000000"


@dataclass
class Palabra:
    texto: str
    inicio: float
    fin: float
    escena: int


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", t)


def alinear(cfg: Config, audio: Path, escenas: list[str]) -> list[Palabra]:
    """Devuelve las palabras DEL GUION (bien escritas) con los tiempos que escuchó Whisper."""
    from faster_whisper import WhisperModel

    import subprocess

    import numpy as np

    # Decodificar con ffmpeg (16 kHz mono float) evita depender de PyAV, que cambia su API seguido.
    pcm = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(audio), "-f", "f32le",
         "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True,
    ).stdout
    muestras = np.frombuffer(pcm, dtype=np.float32)

    # El modelo se guarda dentro del repo (carpeta modelos/, fuera de git: se baja solo la primera vez).
    modelo = WhisperModel(cfg.whisper_modelo, device="cpu", compute_type="int8",
                          download_root=str(cfg.datos.parent / "modelos"))
    segmentos, _ = modelo.transcribe(
        muestras,
        language="es",
        word_timestamps=True,
        initial_prompt=" ".join(escenas),
        vad_filter=False,
    )
    oidas = [w for s in segmentos for w in (s.words or [])]

    guion: list[tuple[str, int]] = []
    for i, escena in enumerate(escenas):
        for tok in escena.replace("...", " ").split():
            if _norm(tok):
                guion.append((tok, i))

    a = [_norm(t) for t, _ in guion]
    b = [_norm(w.word) for w in oidas]
    tiempos: list[tuple[float, float] | None] = [None] * len(guion)
    for bloque in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_matching_blocks():
        for k in range(bloque.size):
            w = oidas[bloque.b + k]
            tiempos[bloque.a + k] = (w.start, w.end)

    # Interpolar las palabras que Whisper escuchó distinto (números, nombres propios).
    total = oidas[-1].end if oidas else 1.0
    i = 0
    while i < len(tiempos):
        if tiempos[i] is not None:
            i += 1
            continue
        j = i
        while j < len(tiempos) and tiempos[j] is None:
            j += 1
        desde = tiempos[i - 1][1] if i > 0 else 0.0
        hasta = tiempos[j][0] if j < len(tiempos) else total
        paso = max(hasta - desde, 0.05) / (j - i)
        for k in range(i, j):
            tiempos[k] = (desde + paso * (k - i), desde + paso * (k - i + 1))
        i = j

    return [Palabra(t, ini, fin, esc) for (t, esc), (ini, fin) in zip(guion, tiempos)]


def tramos_escenas(palabras: list[Palabra], n: int, duracion: float) -> list[tuple[float, float]]:
    """Inicio y fin de cada escena, sin huecos, cubriendo todo el audio."""
    inicios = []
    for i in range(n):
        ps = [p for p in palabras if p.escena == i]
        inicios.append(ps[0].inicio if ps else (inicios[-1] if inicios else 0.0))
    inicios[0] = 0.0
    return [(inicios[i], inicios[i + 1] if i + 1 < n else duracion) for i in range(n)]


def _grupos(palabras: list[Palabra], max_palabras: int = 3, max_chars: int = 16) -> list[list[Palabra]]:
    grupos, actual = [], []
    for p in palabras:
        largo = sum(len(x.texto) + 1 for x in actual) + len(p.texto)
        if actual and (
            len(actual) >= max_palabras or largo > max_chars or p.escena != actual[-1].escena
        ):
            grupos.append(actual)
            actual = []
        actual.append(p)
        if re.search(r"[.,:;?!…]$", p.texto):
            grupos.append(actual)
            actual = []
    if actual:
        grupos.append(actual)
    return grupos


def _t(s: float) -> str:
    s = max(s, 0)
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def _limpio(t: str) -> str:
    t = t.replace("...", "").replace("…", "")
    return re.sub(r"[,;.]$", "", t).replace("{", "(").replace("}", ")")


def escribir_ass(palabras: list[Palabra], destino: Path, hasta: float, titulo: str = "") -> None:
    """Un evento por palabra: el grupo visible con la palabra que se dice en violeta y con 'pop'."""
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Hanken Grotesk ExtraBold,96,{BLANCO},{BLANCO},{NEGRO},&H80000000,0,0,0,0,100,100,0,0,1,7,3,5,80,80,0,1
Style: Titulo,Hanken Grotesk ExtraBold,88,{BLANCO},{BLANCO},{VIOLETA},{VIOLETA},0,0,0,0,100,100,0,0,3,24,0,7,84,84,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = []
    if titulo:
        # Gancho visual desde el primer cuadro: caja blanca arriba, los primeros 3 segundos.
        t = _limpio(titulo).replace("\n", " ")
        lineas.append(
            "Dialogue: 1,0:00:00.00," + _t(min(3.0, hasta)) + r",Titulo,,0,0,0,,{\fad(120,220)\move(84,366,84,330,0,260)}" + t
        )
    pos = r"{\an5\pos(540,1180)}"
    grupos = _grupos([p for p in palabras if p.inicio < hasta])
    for gi, grupo in enumerate(grupos):
        # Nunca encimar dos grupos: el grupo termina cuando empieza el siguiente.
        siguiente = grupos[gi + 1][0].inicio if gi + 1 < len(grupos) else hasta
        fin_grupo = min(grupo[-1].fin + 0.25, siguiente, hasta)
        for k, p in enumerate(grupo):
            ini = p.inicio if k else grupo[0].inicio
            fin = grupo[k + 1].inicio if k + 1 < len(grupo) else fin_grupo
            if fin <= ini:
                continue
            partes = []
            for m, q in enumerate(grupo):
                txt = _limpio(q.texto)
                if m == k:
                    partes.append(
                        r"{\c" + VIOLETA + r"\fscx112\fscy112\t(0,90,\fscx100\fscy100)}" + txt + r"{\c" + BLANCO + r"\fscx100\fscy100}"
                    )
                else:
                    partes.append(txt)
            lineas.append(f"Dialogue: 0,{_t(ini)},{_t(fin)},Sub,,0,0,0,,{pos}" + " ".join(partes))
    destino.write_text(cab + "\n".join(lineas) + "\n", encoding="utf-8")
