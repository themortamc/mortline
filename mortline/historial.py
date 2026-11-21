"""Historial de reels hechos: evita repetir temas, ganchos y clips."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class Historial:
    def __init__(self, carpeta: Path):
        carpeta.mkdir(parents=True, exist_ok=True)
        self.path = carpeta / "historial.json"
        self.reels: list[dict] = []
        if self.path.exists():
            self.reels = json.loads(self.path.read_text(encoding="utf-8")).get("reels", [])

    def combos_usados(self) -> set[str]:
        return {r["combo"] for r in self.reels if r.get("combo")}

    def ganchos(self, n: int = 40) -> list[str]:
        return [r["gancho"] for r in self.reels[-n:] if r.get("gancho")]

    def temas(self, n: int = 40) -> list[str]:
        return [r["tema"] for r in self.reels[-n:] if r.get("tema")]

    def clips_usados(self) -> set[str]:
        return {c for r in self.reels for c in r.get("clips", [])}

    def agregar(self, reel: dict) -> None:
        reel = {"fecha": datetime.now().isoformat(timespec="seconds"), **reel}
        self.reels.append(reel)
        self.path.write_text(
            json.dumps({"reels": self.reels}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
