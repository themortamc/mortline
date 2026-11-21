"""Cliente mínimo para FreeLLMAPI (API compatible con OpenAI)."""

from __future__ import annotations

import json
import re
import time

import requests

from .config import Config


class LLMError(RuntimeError):
    pass


ULTIMO_MODELO = [""]
_CADENA: list = []


def _modelos(cfg: Config) -> list[str]:
    """Modelos para escribir, en orden. Si en FreeLLMAPI existe la cadena «auto:guiones», va primero."""
    modelos = list(cfg.llm_modelos) or [cfg.llm_model]
    if not _CADENA:
        try:
            r = requests.get(f"{cfg.llm_url}/models", headers={"Authorization": f"Bearer {cfg.llm_key}"}, timeout=10)
            ids = {m["id"] for m in r.json().get("data", [])}
            _CADENA.append("auto:guiones" if "auto:guiones" in ids else "")
        except (requests.RequestException, ValueError):
            _CADENA.append("")
    if _CADENA[0] and _CADENA[0] not in modelos:
        modelos.insert(0, _CADENA[0])
    return modelos


def chat(cfg: Config, system: str, user: str, temperature: float = 0.9) -> str:
    if not cfg.llm_key:
        raise LLMError("Falta la clave de FreeLLMAPI (FREELLMAPI_KEY o ~/.freellmapi-key).")
    ultimo = ""
    modelos = _modelos(cfg)
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
                datos = r.json()
                texto = datos["choices"][0]["message"]["content"] or ""
                if texto.strip():
                    ULTIMO_MODELO[0] = datos.get("model") or modelo
                    return texto
            if r.status_code == 429:
                ultimo = f"HTTP 429 ({modelo})"
                continue  # modelo al límite: pasar al siguiente sin esperar
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
