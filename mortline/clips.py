"""Busca y baja material libre de internet: Pixabay / Pexels (videos) u Openverse (fotos CC0)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import Config

UA = {"User-Agent": "mortline/0.1 (+https://github.com/themortamc/mortline)"}


@dataclass
class Material:
    id: str          # ej. "pixabay:12345" (sirve para no repetir clips entre reels)
    path: Path
    es_video: bool
    credito: str


def _bajar(url: str, destino: Path) -> Path:
    if destino.exists() and destino.stat().st_size > 0:
        return destino
    with requests.get(url, headers=UA, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = destino.with_suffix(destino.suffix + ".part")
        with tmp.open("wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        tmp.rename(destino)
    return destino


def _pixabay(cfg: Config, q: str) -> list[dict]:
    r = requests.get(
        "https://pixabay.com/api/videos/",
        params={"key": cfg.pixabay_key, "q": q[:100], "per_page": 30, "safesearch": "true",
                "video_type": "film"},
        timeout=30,
    )
    r.raise_for_status()
    out = []
    for h in r.json().get("hits", []):
        # El reel es 1080×1920: alcanza con ~1080p. "large" suele ser 4K (100-200 MB por clip).
        tamanios = [h["videos"].get(k) or {} for k in ("medium", "large", "small")]
        tamanios = [t for t in tamanios if t.get("url") and min(t.get("width", 0), t.get("height", 0)) >= 720]
        if not tamanios:
            continue
        v = min(tamanios, key=lambda t: abs(min(t["width"], t["height"]) - 1080))
        out.append({
            "id": f"pixabay:{h['id']}", "url": v["url"], "w": v["width"], "h": v["height"],
            "dur": h.get("duration", 0), "tags": h.get("tags", ""),
            "credito": f"Pixabay · {h.get('user', '')} · {h.get('pageURL', '')}",
        })
    return out


def _pexels(cfg: Config, q: str) -> list[dict]:
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": cfg.pexels_key},
        params={"query": q, "per_page": 30, "orientation": "portrait"},
        timeout=30,
    )
    r.raise_for_status()
    out = []
    for v in r.json().get("videos", []):
        archivos = [f for f in v["video_files"] if f.get("height") and f["height"] >= 1280]
        archivos.sort(key=lambda f: f["height"])
        if not archivos:
            continue
        f = archivos[0]
        out.append({
            "id": f"pexels:{v['id']}", "url": f["link"], "w": f["width"], "h": f["height"],
            "dur": v.get("duration", 0), "credito": f"Pexels · {v['user']['name']} · {v['url']}",
        })
    return out


def _openverse_pedir(params: dict) -> list[dict]:
    import time

    r = None
    for intento in range(3):  # la API pública devuelve 504 seguido: reintentar
        try:
            r = requests.get("https://api.openverse.org/v1/images/", headers=UA, params=params, timeout=40)
            if r.status_code < 500:
                break
        except requests.RequestException:
            r = None
        time.sleep(2 * (intento + 1))
    if r is None:
        raise requests.RequestException("Openverse no responde")
    r.raise_for_status()
    return r.json().get("results", [])


def _openverse(q: str) -> list[dict]:
    """Fotos CC0: primero StockSnap (fotos de stock modernas), después el resto de CC0.
    No usa 'dominio público' (pdm): ahí aparecen grabados y pinturas antiguas."""
    base = {"q": q, "license": "cc0", "page_size": 20, "mature": "false", "size": "large"}
    resultados = _openverse_pedir({**base, "source": "stocksnap"})
    if len(resultados) < 6:
        resultados += _openverse_pedir({**base, "category": "photograph"})
    out, vistos = [], set()
    for i in resultados:
        w, h = i.get("width") or 0, i.get("height") or 0
        if i["id"] in vistos or (min(w, h) and (max(w, h) < 900 or max(w, h) > 8000)):
            continue
        vistos.add(i["id"])
        out.append({
            "id": f"openverse:{i['id']}", "url": i["url"], "w": w, "h": h, "dur": 0,
            "credito": f"Openverse · {i.get('creator') or 'anónimo'} · {i.get('license')} · {i.get('foreign_landing_url')}",
        })
    return out


def proveedores(cfg: Config) -> list[str]:
    orden = []
    if cfg.pixabay_key:
        orden.append("pixabay")
    if cfg.pexels_key:
        orden.append("pexels")
    return orden + ["openverse"]


def proveedor(cfg: Config) -> str:
    return " → ".join(proveedores(cfg))


def buscar(cfg: Config, consulta: str, cantidad: int, segundos: float, evitar: set[str],
           cache: Path) -> list[Material]:
    """Devuelve `cantidad` materiales distintos para la consulta (prefiere verticales y largos)."""
    cache.mkdir(parents=True, exist_ok=True)
    fuentes = {"pixabay": _pixabay, "pexels": _pexels, "openverse": lambda _cfg, q: _openverse(q)}
    palabras = consulta.lower().split()
    # La primera palabra es el sujeto que tiene que verse ("barber cutting hair" → barber).
    # Si la búsqueda completa no trae nada, se va achicando sin perder el sujeto.
    consultas = list(dict.fromkeys([" ".join(palabras), " ".join(palabras[:2]), palabras[0]]))
    claves = {w for w in palabras if len(w) > 2}

    def _raiz(w: str) -> str:
        return w[:5]

    def _tags(c: dict) -> set[str]:
        return {_raiz(t) for t in c.get("tags", "").replace(",", " ").lower().split()}

    def muestra_lo_pedido(c: dict, q: str) -> bool:
        # Videos con etiquetas: tienen que incluir el sustantivo de la búsqueda.
        # Así "barber writing on paper" no trae un libro con flores.
        return "tags" not in c or _raiz(q.split()[0]) in _tags(c)

    candidatos: list[dict] = []
    for prov in proveedores(cfg):
        for q in consultas:
            try:
                res = fuentes[prov](cfg, q)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code in (401, 403):
                    break  # clave inválida: probar el próximo proveedor
                continue
            except requests.RequestException:
                continue
            vistos = {x["id"] for x in candidatos}
            candidatos += [dict(c, prov=prov) for c in res
                           if c["id"] not in evitar and c["id"] not in vistos and muestra_lo_pedido(c, q)]
            if len(candidatos) >= cantidad * 2:
                break
        if candidatos:
            break

    def puntaje(c):
        # Lo que más importa es que el clip muestre lo que dice la frase (tags del banco).
        relevancia = 3 * len({_raiz(w) for w in claves} & _tags(c))
        vertical = 2 if c["h"] > c["w"] else 0
        alcanza = 1 if (c["dur"] == 0 or c["dur"] >= segundos) else 0
        return relevancia + vertical + alcanza

    candidatos.sort(key=puntaje, reverse=True)
    elegidos: list[Material] = []
    for c in candidatos:
        if len(elegidos) >= cantidad:
            break
        es_video = c["prov"] != "openverse"
        ext = ".mp4" if es_video else (Path(c["url"].split("?")[0]).suffix or ".jpg")
        nombre = hashlib.sha1(c["id"].encode()).hexdigest()[:16] + ext
        try:
            p = _bajar(c["url"], cache / nombre)
        except requests.RequestException:
            continue
        elegidos.append(Material(c["id"], p, es_video, c["credito"]))
    return elegidos
