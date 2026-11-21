"""Música de fondo: tus mp3 en music/ o, si no hay, loops lofi CC0 bajados de Openverse."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import requests

UA = {"User-Agent": "mortline/0.1 (+https://github.com/themortamc/mortline)"}
EXT = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}
BUSQUEDAS = ["lofi melody loop", "lofi piano loop", "chill lofi", "lofi jazz", "ambient lofi"]
EXCLUIR = re.compile(r"beach|nature|bird|ocean|rain|noise|sfx|voice|vocal|horror|scary|8-?bit|chip", re.I)


def _propios(carpeta: Path) -> list[Path]:
    return [p for p in carpeta.glob("*") if p.suffix.lower() in EXT]


def _bajar_cc0(carpeta: Path, cuantos: int = 6) -> list[Path]:
    destino = carpeta / "cc0"
    destino.mkdir(parents=True, exist_ok=True)
    creditos_path = destino / "creditos.json"
    creditos = json.loads(creditos_path.read_text()) if creditos_path.exists() else {}
    for q in BUSQUEDAS:
        if len(creditos) >= cuantos:
            break
        try:
            r = requests.get(
                "https://api.openverse.org/v1/audio/",
                headers=UA,
                params={"q": q, "license": "cc0", "page_size": 20},
                timeout=30,
            )
            r.raise_for_status()
        except requests.RequestException:
            continue
        for a in r.json().get("results", []):
            if len(creditos) >= cuantos:
                break
            tags = " ".join(t["name"] for t in a.get("tags", []))
            texto = f"{a['title']} {tags}"
            if (a.get("duration") or 0) < 30000 or EXCLUIR.search(texto) or not re.search(r"lo-?fi|chill", texto, re.I):
                continue
            nombre = re.sub(r"[^a-z0-9]+", "-", a["title"].lower()).strip("-")[:40] + ".mp3"
            if nombre in creditos:
                continue
            try:
                with requests.get(a["url"], headers=UA, timeout=60) as resp:
                    resp.raise_for_status()
                    (destino / nombre).write_bytes(resp.content)
            except requests.RequestException:
                continue
            creditos[nombre] = a.get("attribution") or a["foreign_landing_url"]
    creditos_path.write_text(json.dumps(creditos, ensure_ascii=False, indent=2))
    return [destino / n for n in creditos if (destino / n).exists()]


def elegir(carpeta: Path) -> Path | None:
    carpeta.mkdir(parents=True, exist_ok=True)
    temas = _propios(carpeta) or [p for p in (carpeta / "cc0").glob("*") if p.suffix.lower() in EXT]
    if not temas:
        temas = _bajar_cc0(carpeta)
    return random.choice(temas) if temas else None
