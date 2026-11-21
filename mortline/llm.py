"""Cliente mínimo para FreeLLMAPI (API compatible con OpenAI)."""

from __future__ import annotations

import json
import re
import time

import requests

from .config import Config


class LLMError(RuntimeError):
    pass


def chat(cfg: Config, system: str, user: str, temperature: float = 0.9) -> str:
    if not cfg.llm_key:
        raise LLMError("Falta la clave de FreeLLMAPI (FREELLMAPI_KEY o ~/.freellmapi-key).")
    ultimo = ""
    modelos = list(cfg.llm_modelos) or [cfg.llm_model]
    # Los modelos gratis a veces están saturados (rate limit / timeout): se rota entre los
    # preferidos y "auto" varias vueltas, esperando cada vez un poco más.
    if "auto" not in modelos:
        modelos.append("auto")
    intentos = len(modelos) * 3
    for intento in range(intentos):
        modelo = modelos[intento % len(modelos)]
        if intento and intento % len(modelos) == 0:
            time.sleep(15 * (intento // len(modelos)))
        try:
            r = requests.post(
                f"{cfg.llm_url}/chat/completions",
                headers={"Authorization": f"Bearer {cfg.llm_key}"},
                json={
                    "model": modelo,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=180,
            )
            if r.status_code == 200:
                texto = r.json()["choices"][0]["message"]["content"] or ""
                if texto.strip():
                    return texto
            ultimo = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as exc:
            ultimo = str(exc)
            if "Connection refused" in ultimo:
                break  # la app está cerrada: no tiene sentido reintentar
        time.sleep(2)
    raise LLMError(
        f"FreeLLMAPI no respondió ({ultimo[:200]}). ¿Está abierta la app de escritorio en {cfg.llm_url}?"
    )


def chat_json(cfg: Config, system: str, user: str, temperature: float = 0.9) -> dict:
    """Pide JSON y lo extrae aunque el modelo lo envuelva en ```json o texto."""
    for _ in range(3):
        texto = chat(cfg, system, user, temperature)
        datos = extraer_json(texto)
        if datos is not None:
            return datos
        user += "\n\nIMPORTANTE: respondé SOLO con el objeto JSON, sin texto alrededor."
    raise LLMError("El modelo no devolvió un JSON válido después de 3 intentos.")


def extraer_json(texto: str) -> dict | None:
    texto = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.M).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio != -1 and fin > inicio:
        try:
            return json.loads(texto[inicio : fin + 1])
        except json.JSONDecodeError:
            return None
    return None
