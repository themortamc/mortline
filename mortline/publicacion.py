"""Lo que acompaña al video al publicarlo: caption con hashtags curados y portada para la grilla."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .config import Config

# Hashtags curados por rubro (bien escritos y que la gente realmente busca). Máximo 5 por reel.
HASHTAGS_RUBRO = {
    "ferreterias": ["#ferreteria", "#ferreterias"],
    "repuestos": ["#repuestos", "#repuestosautomotor"],
    "gastronomia": ["#gastronomia", "#restaurantes"],
    "restaurantes": ["#gastronomia", "#restaurantes"],
    "indumentaria": ["#indumentaria", "#tiendaderopa"],
    "barberias": ["#barberia", "#barberos"],
    "kioscos": ["#kiosco", "#almacen"],
    "talleres": ["#tallermecanico", "#mecanica"],
    "talleres-mecanicos": ["#tallermecanico", "#mecanica"],
    "gimnasios": ["#gimnasio", "#fitness"],
    "clinicas": ["#consultorio", "#salud"],
    "distribuidoras": ["#distribuidora", "#mayorista"],
    "empresas": ["#pymes", "#empresas"],
    "general": ["#comercio", "#negocios"],
}
HASHTAGS_BASE = ["#emprendedoresargentinos", "#pymesargentinas", "#mendoza"]
# Para productos de rubro "general": hashtags según de qué trata la planilla.
HASHTAGS_PRODUCTO = {
    "fiado": ["#almacen", "#fiado"], "calculadora": ["#mercadopago", "#precios"],
    "pedidos": ["#ventasporwhatsapp", "#emprendimiento"], "pagar-y-cobrar": ["#flujodecaja", "#finanzas"],
    "ventas-y-caja": ["#cajadiaria", "#ventas"], "stock": ["#controldestock", "#inventario"],
    "lista-de-precios": ["#listadeprecios", "#precios"], "presupuestos": ["#presupuestos", "#ventas"],
    "pack": ["#planillas", "#emprendimiento"],
}
HASHTAGS_PLANILLA = ["#planillasexcel", "#googlesheets"]

CIERRE_CTA = {
    "whatsapp": "Pedí tu demo gratis por WhatsApp: el link está en el perfil.",
    "comentario": "Comentá DEMO y te escribo para armarte la tuya.",
    "guardar": "Guardalo para tenerlo a mano y seguime para más ideas así.",
}
_CTA_LLM = re.compile(r"(whatsapp|perfil|escribime|coment[aá]|guard[aá]lo|mand[aá](le|selo)|link|tienda)", re.I)


def _rubro(datos: dict, producto_info: dict | None) -> str:
    if producto_info:
        return producto_info.get("rubro", "general")
    combo = datos.get("combo") or ""
    return combo.split("/")[0] if "/" in combo else "general"


def caption(cfg: Config, datos: dict, producto: str | None) -> str:
    from .guion import RUBROS, datos_producto

    info = datos_producto(cfg, producto) if producto else None
    rubro = _rubro(datos, info)
    partes = [datos.get("gancho", "").strip()]
    if info:
        partes.append(info["resumen"])
        partes.append("\n".join("• " + x for x in info.get("incluye", [])[:3]))
        precio = "$" + f"{info['precio']:,}".replace(",", ".")
        partes.append(f"Precio: {precio}, pago único. Funciona en Excel y Google Sheets.")
        partes.append("La conseguís en la tienda de mortups.com.ar (link en el perfil).")
        quien = info.get("_rubro_txt", "").lower()
        destinatario = f"alguien con {quien}" if quien and "cualquier" not in quien else "alguien que tenga un negocio"
        propios = next((v for k, v in HASHTAGS_PRODUCTO.items() if k in producto), None) if rubro == "general" else None
        tags = (propios or HASHTAGS_RUBRO.get(rubro, HASHTAGS_RUBRO["general"]))[:2] + HASHTAGS_PLANILLA[:1] + HASHTAGS_BASE[:2]
    else:
        # Del caption del modelo nos quedamos con lo informativo; el llamado lo ponemos nosotros (igual que en el video).
        frases = re.split(r"(?<=[.!?])\s+", (datos.get("caption") or "").strip())
        util = " ".join(f for f in frases if f and not _CTA_LLM.search(f))
        partes.append(util)
        partes.append(CIERRE_CTA.get(datos.get("cta", ""), CIERRE_CTA["whatsapp"]))
        txt = RUBROS.get(rubro, "")
        destinatario = f"alguien que tenga {txt.split(' y ')[0]}" if txt else "alguien que tenga un negocio"
        tags = HASHTAGS_RUBRO.get(rubro, HASHTAGS_RUBRO["general"])[:2] + HASHTAGS_BASE
    partes.append(f"Mandáselo a {destinatario}.")
    cuerpo = "\n\n".join(p for p in partes if p)
    return f"{cuerpo}\n\n{' '.join(dict.fromkeys(tags[:5]))}\n"


def _cuadro_fondo(materiales, trabajo: Path) -> Path | None:
    """Primer cuadro real del reel (clip o foto de la primera escena) para el fondo de la portada."""
    for mats in materiales:
        for m in mats:
            if getattr(m, "estilo", "") == "captura":
                continue
            destino = trabajo / "portada_fondo.jpg"
            entrada = ["-ss", "1", "-i", str(m.path)] if m.es_video else ["-i", str(m.path)]
            r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *entrada, "-frames:v", "1",
                                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                                str(destino)], capture_output=True)
            if r.returncode == 0 and destino.exists():
                return destino
    return None


def portada(cfg: Config, datos: dict, materiales, destino: Path, trabajo: Path, fondo: Path | None = None) -> None:
    """Portada 1080×1920 para la grilla: el título grande dentro del recorte 3:4 que muestra el perfil."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    W, H = 1080, 1920
    fondo_path = fondo or _cuadro_fondo(materiales, trabajo)
    if fondo_path:
        img = Image.open(fondo_path).convert("RGB").filter(ImageFilter.GaussianBlur(3))
        img = Image.blend(img, Image.new("RGB", (W, H), (14, 10, 22)), 0.55)
    else:
        img = Image.new("RGB", (W, H), (14, 10, 22))
    d = ImageDraw.Draw(img)
    fuerte = ImageFont.truetype(str(cfg.assets / "fonts" / "HankenGrotesk-ExtraBold.ttf"), 118)
    media = ImageFont.truetype(str(cfg.assets / "fonts" / "HankenGrotesk-SemiBold.ttf"), 50)

    titulo = (datos.get("titulo") or datos.get("gancho") or "").strip()
    palabras, lineas, actual = titulo.split(), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if d.textlength(prueba, font=fuerte) <= 900 or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    alto_linea, pad = 150, 26
    total = len(lineas) * alto_linea
    y = (H - total) // 2 - 60  # centrado dentro del recorte 3:4 de la grilla (y 240–1680)
    for linea in lineas:
        ancho = d.textlength(linea, font=fuerte)
        x = (W - ancho) / 2
        d.rounded_rectangle((x - pad, y - 8, x + ancho + pad, y + alto_linea - 22), radius=18, fill=(139, 44, 255))
        d.text((x, y - 4), linea, font=fuerte, fill="white")
        y += alto_linea
    sub = "mortups.com.ar"
    d.text(((W - d.textlength(sub, font=media)) / 2, y + 40), sub, font=media, fill=(230, 222, 245))
    img.save(destino, quality=92)
