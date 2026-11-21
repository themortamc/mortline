"""Locución con GGNarrator (Gemini TTS, rioplatense)."""

from __future__ import annotations

import base64
import time
from pathlib import Path

import requests

from .config import Config

ESTILO = (
    "Locutor joven de Mendoza, cercano y seguro, español rioplatense natural con voseo. "
    "Ritmo ágil de reel de Instagram, conversacional, como si le hablara a un comerciante conocido. "
    "Gancho con intriga en la primera frase, énfasis natural en lo concreto, cierre firme y amable. "
    "Nada de locutor de radio antiguo ni tono de publicidad exagerado."
)


class VozError(RuntimeError):
    pass


def generar(cfg: Config, texto: str, destino: Path, voz: str | None = None) -> float:
    if not cfg.ggnarrator_url:
        raise VozError("Falta GGNARRATOR_URL en el .env.")
    ultimo = ""
    for intento in range(6):
        try:
            r = requests.post(
                f"{cfg.ggnarrator_url}/api/tts/generate",
                json={"text": texto, "style": ESTILO, "voiceName": voz or cfg.voz, "autoProsody": True},
                timeout=240,
            )
            if r.status_code == 200:
                datos = r.json()
                destino.write_bytes(base64.b64decode(datos["audioBase64"]))
                return float(datos.get("durationSeconds") or 0)
            ultimo = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code == 429:
                # Límite de Gemini TTS: esperar y reintentar (20 s, 40 s, 60 s...).
                print(f"   GGNarrator está al límite de pedidos; espero {20 * (intento + 1)} s…", flush=True)
                time.sleep(20 * (intento + 1))
                continue
        except requests.RequestException as exc:
            ultimo = str(exc)
        time.sleep(5 * (intento + 1))
    raise VozError(f"GGNarrator falló: {ultimo}")
