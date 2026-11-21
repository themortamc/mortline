"""Elige un tema que no se haya hecho y escribe el guion con FreeLLMAPI."""

from __future__ import annotations

import random
import re

from . import llm
from .config import Config
from .historial import Historial

RUBROS = {
    "ferreterias": "ferreterías",
    "repuestos": "casas de repuestos de autos y motos",
    "gastronomia": "restaurantes, rotiserías y bares",
    "indumentaria": "locales de ropa e indumentaria",
    "barberias": "barberías y peluquerías",
    "kioscos": "kioscos y almacenes",
    "talleres": "talleres mecánicos",
    "gimnasios": "gimnasios",
    "clinicas": "consultorios y clínicas",
    "distribuidoras": "distribuidoras y mayoristas",
}

SERVICIOS = {
    "catalogo": "catálogo web con pedidos que llegan armados al WhatsApp",
    "menu-qr": "menú digital con QR",
    "pos": "sistema de registro de ventas y panel de ventas",
    "anuncios": "campañas de anuncios en Instagram, Facebook, Google y TikTok",
    "planillas": "planillas digitales hechas para el rubro",
    "demo": "la demo gratis con sus propios productos en 24 a 72 horas",
}

# Qué servicios tienen sentido en cada rubro (el resto usa los generales).
SOLO_EN = {"menu-qr": {"gastronomia"}}

FORMATOS = {
    "dolor": "Arrancá por un dolor concreto y cotidiano del rubro y mostrá cómo se resuelve.",
    "error": "Contá un error común que comete el dueño del rubro y qué hacer en su lugar.",
    "antes-despues": "Contrastá cómo es un día del negocio antes y después de tenerlo.",
    "pregunta": "Abrí con una pregunta directa que el dueño se responda 'sí, me pasa'.",
    "mito": "Desarmá una creencia típica (\"eso es para empresas grandes\", \"es caro\", \"es complicado\").",
    "caso": "Contá brevemente uno de los casos reales (Todo y Más o Repuestos San Isidro) sin inventar datos.",
    "tip": "Dá un consejo útil y accionable para el rubro, y recién al final mencioná mortups.",
}

# Un solo llamado por reel, rotando (la investigación: un CTA por reel; los comentarios también
# empujan la distribución; los "guardar" suman en contenido útil). WhatsApp va el doble de seguido.
CTAS = {
    "whatsapp": {
        "voz": 'invitá a escribir por WhatsApp para pedir la demo gratis (el link está en el perfil)',
        "placa": "Pedí tu demo gratis por WhatsApp",
    },
    "comentario": {
        "voz": 'pedí que comenten la palabra DEMO y que Lautaro le escribe para armarle la suya',
        "placa": "Comentá DEMO y te escribo",
    },
    "guardar": {
        "voz": 'pedí que lo guarden para tenerlo a mano y que sigan la cuenta para más consejos así',
        "placa": "Guardalo y seguime",
    },
}
CTAS["producto"] = {
    "voz": 'invitá a conseguir la planilla en la tienda de mortups.com.ar (el link está en el perfil)',
    "placa": "Conseguila en la tienda",
}
ROTACION = ["whatsapp", "comentario", "whatsapp", "guardar"]

PRODUCTO = """Este reel vende UN producto digital de la tienda de mortups (no los servicios de web):
Nombre: {nombre}
Qué es: {resumen}
Para quién: {para}
Qué incluye:
{incluye}
Precio: {precio}, pago único (en este reel SÍ podés decir el precio exacto).
Formato: planilla para Excel y Google Sheets, se compra por WhatsApp y te ayudan a dejarla andando.

Reglas extra para este reel:
- El gancho (primera escena) es el problema concreto que resuelve, como lo vive el dueño, en una pregunta
  o una frase que duela ("¿Cobrás en cuotas y no sabés cuánto te queda?"). Nunca empieces explicando la planilla.
- Mostrá 2 o 3 cosas puntuales que hace la planilla (de la lista de qué incluye), con ejemplos concretos.
- Exactamente 2 escenas tienen "buscar": "CAPTURA" (ahí se ve la planilla de verdad en pantalla):
  usalas cuando la frase habla de lo que muestra o calcula la planilla. El resto, búsquedas de stock del rubro.
- La primera y la última escena NUNCA son "CAPTURA" (arrancan y cierran con imagen real del rubro).
- El "buscar" de la primera escena muestra el PROBLEMA del gancho de forma concreta y filmable
  (ej: "notebook handwritten accounts", "calculator receipts", "phone many messages"), no una persona genérica."""

CIERRES_PRODUCTO = ["La conseguís en la tienda de mortups... el link está en el perfil.",
                    "Está en la tienda de mortups, con el link en el perfil.",
                    "Pedila en la tienda de mortups... link en el perfil."]


def datos_producto(cfg: Config, slug: str) -> dict:
    import json

    prods = json.loads(cfg.productos.read_text(encoding="utf-8"))
    for p in prods["productos"]:
        if p["slug"] == slug:
            p["_rubro_txt"] = prods["rubros"].get(p["rubro"], p["rubro"])
            return p
    raise ValueError(f"No existe el producto «{slug}». Opciones: " + ", ".join(p["slug"] for p in prods["productos"]))


def elegir_cta(hist: Historial) -> str:
    return ROTACION[len(hist.reels) % len(ROTACION)]


SISTEMA = """Sos guionista de reels verticales de 20 a 30 segundos para Instagram y TikTok.
Escribís para la marca descripta en el brief y respetás TODAS sus reglas.

{brief}

Reglas del guion (pensadas para el algoritmo de Reels/TikTok/Shorts: que lo vean completo y lo compartan):
- Entre 45 y 65 palabras en total (unos 20 segundos). Más corto = más gente lo ve completo.
- La primera escena es el gancho hablado: máximo 10 palabras, concreto del rubro, que genere curiosidad o
  identificación inmediata ("me pasa"). Nada de saludos ni presentaciones ("Hola, soy...").
- 4 a 6 escenas. Cada escena es 1 o 2 frases cortas. Cada escena aporta algo nuevo: no rellenes.
- Tiene que ser útil o muy identificable, algo que el dueño quiera mandarle a otro comerciante.
- La última escena es el llamado que se indica en el pedido (uno solo). Corta y firme.
- Usá "..." para marcar una pausa natural de respiración (máximo 3 en todo el guion).
- Escribí los números como se dicen ("24 a 72 horas" está bien).
- "titulo": texto que se ve arriba en pantalla los primeros 3 segundos, máximo 6 palabras.
  Complementa el gancho hablado (no lo repite palabra por palabra) y nombra el rubro o el problema.
- "buscar" es una búsqueda EN INGLÉS de 2 o 3 palabras para un banco de videos de stock.
  La PRIMERA palabra es siempre el sujeto o lugar que tiene que verse (barber, kitchen, cashier, mechanic,
  phone, store), y después el detalle: "barber cutting hair", "kitchen chef cooking", "phone typing message".
  algo concreto y filmable que acompañe la frase (ej: "hardware store shelves", "phone whatsapp chat",
  "cashier counter shop"). Nada abstracto ("success", "growth"). Variá las búsquedas entre escenas.
  Al menos la mitad de las escenas tienen que mostrar el rubro mismo: el local, el dueño o el empleado
  trabajando (ej. barbería: "barber shop", "barber cutting hair"; ferretería: "tools shop", "tools shelf", "screws bolts"
  — nunca "hardware", que trae computadoras).
- "caption": 1 a 3 frases con voseo que incluyan las palabras que un dueño buscaría
  (ej: "catálogo web para ferretería", "vender por WhatsApp"), y una línea final que invite a
  mandárselo a alguien que tenga ese tipo de negocio.
- "hashtags": 3 a 5, específicos (rubro, ciudad/país, tema). Nada de #viral ni #fyp.

Respondé SOLO con este JSON:
{{"tema": "...", "titulo": "...", "escenas": [{{"texto": "...", "buscar": "..."}}],
  "caption": "texto para la publicación, 1 a 3 frases, voseo, con un llamado a escribir",
  "hashtags": ["#...", "..."]}}"""

EDITOR = """Sos editor de guiones de reels. Recibís un guion en JSON y el brief de la marca.
Revisalo y devolvé el MISMO formato JSON corregido:
- Que respete el brief (sin datos inventados, sin precios, sin frases de IA, voseo rioplatense, primera persona singular).
- Que tenga entre 45 y 65 palabras sumando todas las escenas.
- Que el "titulo" tenga máximo 6 palabras y no repita literal el gancho hablado.
- Que el gancho sea específico del rubro y genere curiosidad (no genérico).
- Que suene hablado, natural, como lo diría un mendocino de 25 años, no leído.
- Que cada "buscar" sea concreto, filmable y en inglés, de 2 o 3 palabras comunes (ej: "hardware store", "cashier counter").
- Si una escena tiene "buscar": "CAPTURA", dejala exactamente así (ahí va la captura de la planilla).
- Que la última escena mantenga el MISMO llamado que trae el guion (no lo cambies por otro).
- Que todo tenga sentido lógico y sea coherente entre escenas (horarios, situaciones reales del rubro).
- Que el "titulo" use palabras reales y comunes, y que se entienda solo.
- Datos exactos del brief, sin redondear ni inventar: la demo es "en 24 a 72 horas" (nunca otro plazo).
- Nada de palabras en inglés en el guion, el título ni el caption (no: "ads", "leads"; sí se puede: marketing, WhatsApp, QR).
- Ortografía perfecta con tildes (pizzería, catálogo, también, está).
- Que no haya palabras de otros países (ver la lista de palabras que NO se usan) ni errores de ortografía,
  tampoco en los hashtags.
Si ya está bien, devolvelo igual. Respondé SOLO con el JSON.

Brief:
{brief}"""


def elegir_combo(hist: Historial, rubro: str | None = None) -> tuple[str, str, str]:
    usados = hist.combos_usados()
    rubros = [rubro] if rubro else list(RUBROS)
    opciones = []
    for r in rubros:
        for s in SERVICIOS:
            if s in SOLO_EN and r not in SOLO_EN[s]:
                continue
            for f in FORMATOS:
                if f"{r}/{s}/{f}" not in usados:
                    opciones.append((r, s, f))
    if not opciones:
        raise RuntimeError("Ya se hicieron todas las combinaciones de tema. Pasale un tema a mano.")
    # Preferir rubros y formatos que se usaron menos últimamente.
    recientes = [x["combo"].split("/") for x in hist.reels[-15:] if x.get("combo")]
    def peso(o):
        return 1 + sum(o[0] == x[0] for x in recientes) * 2 + sum(o[2] == x[2] for x in recientes)
    minimo = min(peso(o) for o in opciones)
    return random.choice([o for o in opciones if peso(o) == minimo])


def contar_palabras(datos: dict) -> int:
    return sum(len(re.findall(r"\w+", e["texto"])) for e in datos["escenas"])


def escribir(cfg: Config, hist: Historial, tema: str | None = None, rubro: str | None = None,
             producto: str | None = None) -> dict:
    brief = cfg.marca.read_text(encoding="utf-8")
    combo = None
    if producto:
        p = datos_producto(cfg, producto)
        precio = "$" + f"{p['precio']:,}".replace(",", ".") if p.get("precio") else "a consultar"
        pedido = PRODUCTO.format(nombre=p["nombre"], resumen=p["resumen"], para=p["_rubro_txt"],
                                 incluye="\n".join("- " + x for x in p.get("incluye", [])), precio=precio)
        combo = f"producto/{producto}"
    elif tema:
        pedido = f"Tema del reel: {tema}"
    else:
        r, s, f = elegir_combo(hist, rubro)
        combo = f"{r}/{s}/{f}"
        pedido = (
            f"Rubro: {RUBROS[r]}.\nQué mostrar: {SERVICIOS[s]}.\nEnfoque: {FORMATOS[f]}"
        )
    cta = "producto" if producto else elegir_cta(hist)
    pedido += f"\nLlamado final (última escena): {CTAS[cta]['voz']}."
    previos = hist.ganchos(30)
    if previos:
        pedido += "\n\nGanchos ya usados (no repitas ni parafrasees ninguno):\n- " + "\n- ".join(previos)

    datos = llm.chat_json(cfg, SISTEMA.format(brief=brief), pedido, temperature=1.0)
    datos = llm.chat_json(
        cfg, EDITOR.format(brief=brief), "Guion a revisar:\n" + _dump(datos), temperature=0.4
    )
    for _ in range(2):
        n = contar_palabras(datos)
        if 40 <= n <= 72:
            break
        datos = llm.chat_json(
            cfg,
            EDITOR.format(brief=brief),
            f"Este guion tiene {n} palabras; dejalo entre 45 y 65 sin perder el gancho:\n" + _dump(datos),
            temperature=0.4,
        )
    _validar(datos)
    if producto:
        # Cierre fijo y coherente con la placa; capturas nunca en la primera ni en la última escena.
        datos["escenas"][-1]["texto"] = CIERRES_PRODUCTO[len(hist.reels) % len(CIERRES_PRODUCTO)]
        for e in (datos["escenas"][0], datos["escenas"][-1]):
            if e["buscar"].strip().upper() == "CAPTURA":
                e["buscar"] = "store owner smiling"
        # Siempre 2 escenas con la planilla real (las del medio), aunque el modelo ponga menos.
        medio = list(range(1, len(datos["escenas"]) - 1))
        con = [i for i in medio if datos["escenas"][i]["buscar"].strip().upper() == "CAPTURA"]
        for i in medio:
            if len(con) >= 2:
                break
            if i not in con:
                datos["escenas"][i]["buscar"] = "CAPTURA"
                con.append(i)
        datos["gancho"] = datos["escenas"][0]["texto"]
    datos["combo"] = combo
    datos["modelo"] = llm.ULTIMO_MODELO[0]
    datos["cta"] = cta
    return datos


def texto_locucion(datos: dict) -> str:
    return "\n\n".join(e["texto"].strip() for e in datos["escenas"])


def _dump(d: dict) -> str:
    import json

    return json.dumps(d, ensure_ascii=False)


def _validar(d: dict) -> None:
    if not isinstance(d.get("escenas"), list) or len(d["escenas"]) < 3:
        raise llm.LLMError("El guion vino sin escenas suficientes.")
    for e in d["escenas"]:
        if not e.get("texto") or not e.get("buscar"):
            raise llm.LLMError("Hay una escena sin texto o sin búsqueda.")
    d.setdefault("tema", d["escenas"][0]["texto"])
    d["gancho"] = d["escenas"][0]["texto"]
    d.setdefault("titulo", "")
    d.setdefault("caption", "")
    d.setdefault("hashtags", [])
