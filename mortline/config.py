"""Configuración: se lee de .env (en la raíz del repo) y de variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class Config:
    llm_url: str
    llm_key: str
    llm_model: str
    llm_modelos: tuple[str, ...]
    ggnarrator_url: str
    voz: str
    pixabay_key: str
    pexels_key: str
    web: str
    salida: Path
    whisper_modelo: str
    marca: Path
    musica: Path
    datos: Path
    assets: Path
    productos: Path
    capturas: Path


def _clave(nombre: str) -> str:
    """Ignora valores de relleno tipo 'tu_clave' o 'xxx'."""
    v = os.environ.get(nombre, "").strip()
    if len(v) < 16 or v.lower() in {"tu_clave", "your_key", "changeme"} or set(v) <= {"x", "X"}:
        return ""
    return v


def cargar() -> Config:
    _load_dotenv(ROOT / ".env")
    key = os.environ.get("FREELLMAPI_KEY", "")
    key_file = Path(os.environ.get("FREELLMAPI_KEY_FILE", "~/.freellmapi-key")).expanduser()
    if not key and key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
    return Config(
        llm_url=os.environ.get("FREELLMAPI_URL", "http://127.0.0.1:31416/v1").rstrip("/"),
        llm_key=key,
        llm_model=os.environ.get("MORTLINE_MODELO", "auto"),
        # Para escribir se prueban primero modelos fuertes; si no responden, "auto" elige otro.
        llm_modelos=tuple(m.strip() for m in os.environ.get(
            "MORTLINE_MODELOS", "gemini-3.8-flash,deepseek-v4-pro,glm-5.3,auto").split(",") if m.strip()),
        ggnarrator_url=os.environ.get("GGNARRATOR_URL", "").rstrip("/"),
        voz=os.environ.get("MORTLINE_VOZ", "Puck"),
        pixabay_key=_clave("PIXABAY_API_KEY"),
        pexels_key=_clave("PEXELS_API_KEY"),
        web=os.environ.get("MORTLINE_WEB", "mortups.com.ar"),
        salida=Path(os.environ.get("MORTLINE_SALIDA", "~/Downloads/job/reels")).expanduser(),
        whisper_modelo=os.environ.get("MORTLINE_WHISPER", "small"),
        marca=ROOT / "marca" / "mortups.md",
        musica=ROOT / "music",
        datos=ROOT / "data",
        assets=ROOT / "assets",
        productos=Path(os.environ.get("MORTLINE_PRODUCTOS", "~/repos/mortups/tools/productos.json")).expanduser(),
        capturas=Path(os.environ.get("MORTLINE_CAPTURAS", "~/Downloads/job/productos-mortups/capturas")).expanduser(),
    )
