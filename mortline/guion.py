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

# Formatos narrativos: cada uno cambia la estructura del guion y qué escenas conviene mostrar.
FORMATOS = {
    "problema-solucion": dict(
        guion="Problema concreto y cotidiano del rubro -> lo que le cuesta al dueño -> giro -> cómo se resuelve -> cierre.",
        escenas="Gancho titular; el problema con 'chat' o 'antes_despues'; la solución con 'flujo'; un detalle con 'pasos' o 'dato'; remate titular."),
    "mito-verdad": dict(
        guion="Arrancá con una creencia equivocada que repite el dueño del rubro (\"es caro\", \"es para empresas grandes\", \"es complicado\"); desarmala con la verdad y una prueba concreta; cierre.",
        escenas="Usá la plantilla 'mito' (mito tachado y la verdad) para el mito principal; 'dato' o 'flujo' para la prueba; remate titular."),
    "top3-errores": dict(
        guion="Los 3 errores más comunes que comete el dueño del rubro, dichos como 'primer error', 'segundo error', 'tercer error', cada uno concreto, y qué hacer en cambio.",
        escenas="Gancho titular con el número; una escena 'titular' por error (con 'Error 1', 'Error 2'...) o 'mito'; 'pasos' para resumir; remate titular."),
    "cliente-tipo": dict(
        guion="Historia breve de un dueño tipo del rubro (genérico: 'un dueño de una ferretería', sin nombre propio, sin cifras inventadas): su situación, el problema, qué cambió y cómo le fue (cualitativo).",
        escenas="'chat' para el cliente que pregunta, 'antes_despues', 'ticket' o 'flujo' para lo que cambió; remate titular."),
    "antes-despues": dict(
        guion="Contraste de un día del negocio antes y después de tenerlo armado; dos o tres contrastes concretos, uno por frase.",
        escenas="'antes_despues' al menos dos veces con contrastes distintos; 'dato' o 'ticket'; remate titular."),
    "tutorial-3-pasos": dict(
        guion="Tutorial de 3 pasos numerados que el dueño puede aplicar hoy ('primero', 'segundo', 'tercero'), y recién al final mortups.",
        escenas="'pasos' para el panorama; una escena por paso ('celdas', 'ticket', 'chat' o 'titular'); remate titular."),
    "dato-sorprendente": dict(
        guion="Un dato o hecho llamativo y verificable (de los hechos del brief o de sentido común, sin porcentajes ni cifras inventadas), por qué importa y qué hacer.",
        escenas="'dato' para la cifra del brief; 'grafico' o 'antes_despues' para la consecuencia; remate titular."),
    "pregunta": dict(
        guion="Abrí con una pregunta directa que el dueño se conteste 'sí, me pasa'; encadená una o dos preguntas más y respondelas; el cierre vuelve a la pregunta.",
        escenas="'titular' con icono 'circle-help' para las preguntas; 'chat' para la respuesta; 'flujo' o 'pasos' para la solución; remate titular."),
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


SISTEMA = """Sos guionista de reels verticales de 30 a 40 segundos para Instagram y TikTok.
Escribís para la marca descripta en el brief y respetás TODAS sus reglas.

{brief}

Reglas del guion (pensadas para el algoritmo de Reels/TikTok/Shorts: que lo vean completo y lo compartan):
- Entre 105 y 122 palabras en total. El narrador dice unas 3,2 palabras por segundo: con menos de 100 palabras el reel no llega a 30 s y se descarta.
  Cada frase aporta algo nuevo (ejemplo, detalle del rubro, consecuencia); nada de relleno.
- La primera escena es el gancho hablado, dicho en el primer segundo: máximo 10 palabras, concreto del rubro, que genere curiosidad o
  identificación inmediata ("me pasa"). Nada de saludos ni presentaciones ("Hola, soy...").
- 9 a 12 escenas. Cada escena es 1 o 2 frases cortas. Cada escena aporta algo nuevo: no rellenes.
- Seguí la estructura del formato narrativo que se pide, con mortups recién hacia el final y el llamado como cierre.
  Antes del remate o del giro poné una pausa con "..." (el silencio hace que se escuche mejor).
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
- Que tenga entre 105 y 125 palabras sumando todas las escenas (menos de 100 no alcanza los 30 s).
- Que el "titulo" tenga máximo 6 palabras y no repita literal el gancho hablado.
- Que el gancho (primera escena) sea específico del rubro, genere curiosidad (no genérico) y tenga máximo 10 palabras.
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


def elegir_formato(hist: Historial, forzado: str | None = None, ultimos: int = 4) -> str:
    """Formato narrativo que no se repita en los últimos `ultimos` reels (o el que se pidió con --formato)."""
    if forzado:
        return forzado
    usados = [r.get("formato") for r in hist.reels[-ultimos:]]
    libres = [f for f in FORMATOS if f not in usados]
    return random.choice(libres or list(FORMATOS))


def elegir_combo(hist: Historial, formato: str, rubro: str | None = None) -> tuple[str, str]:
    usados = hist.combos_usados()
    rubros = [rubro] if rubro else list(RUBROS)
    opciones = [(r, s) for r in rubros for s in SERVICIOS
                if not (s in SOLO_EN and r not in SOLO_EN[s]) and f"{r}/{s}/{formato}" not in usados]
    if not opciones:  # todo usado con este formato: se permite repetir la combinación
        opciones = [(r, s) for r in rubros for s in SERVICIOS if not (s in SOLO_EN and r not in SOLO_EN[s])]
    # Preferir rubros y servicios que se usaron menos últimamente (variedad de rubro y de tema).
    recientes = [c for c in (x["combo"].split("/") for x in hist.reels[-12:] if x.get("combo")) if len(c) == 3]
    def peso(o):
        return 1 + sum(o[0] == x[0] for x in recientes) * 3 + sum(o[1] == x[1] for x in recientes)
    minimo = min(peso(o) for o in opciones)
    return random.choice([o for o in opciones if peso(o) == minimo])


def contar_palabras(datos: dict) -> int:
    return sum(len(re.findall(r"\w+", e["texto"])) for e in datos["escenas"])


MIN_VOZ = 30.0           # segundos de locución mínimos
PALABRAS_SEG = 3.2       # velocidad real medida de GGNarrator (palabras por segundo)
RANGO_PALABRAS = (104, 126)


def _cierre_producto(datos: dict, hist: Historial) -> None:
    """Cierre fijo y coherente con la placa; capturas nunca en la primera ni en la última escena."""
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


def _ajustar_largo(cfg: Config, brief: str, datos: dict, minimo: int, maximo: int, objetivo: int = 112) -> dict:
    """Lleva el guion al largo pedido (hasta 3 intentos) y se queda con el mejor: los modelos gratis suelen acortar."""
    mejor = datos
    for _ in range(3):
        n = contar_palabras(datos)
        if abs(n - objetivo) < abs(contar_palabras(mejor) - objetivo):
            mejor = datos
        if minimo <= n <= maximo:
            return datos
        if n < minimo:
            falta = objetivo - n
            pedido = (f"Este guion tiene {n} palabras y necesito {objetivo}: agregale unas {falta} palabras. "
                      f"Sumá {max(2, falta // 11)} escenas nuevas de 10 a 15 palabras cada una en el medio (ejemplos concretos "
                      "del rubro, una consecuencia, un detalle útil, sin cifras inventadas) y no toques el gancho ni el llamado "
                      "final. Devolvé el JSON completo, con todas las escenas:\n")
        else:
            pedido = f"Este guion tiene {n} palabras; dejalo en unas {objetivo} sin perder el gancho ni el llamado final:\n"
        datos = llm.chat_json(cfg, EDITOR.format(brief=brief), pedido + _dump(datos), temperature=0.6)
    return datos if abs(contar_palabras(datos) - objetivo) <= abs(contar_palabras(mejor) - objetivo) else mejor


def escribir(cfg: Config, hist: Historial, tema: str | None = None, rubro: str | None = None,
             producto: str | None = None, estilo: str = "stock", formato: str | None = None,
             ampliar: tuple[dict, float] | None = None) -> dict:
    """Guion nuevo. Con `ampliar=(guion_anterior, segundos_de_voz)` reescribe el anterior más largo."""
    brief = cfg.marca.read_text(encoding="utf-8")
    if ampliar:
        previo, dur = ampliar
        n = contar_palabras(previo)
        objetivo = min(max(int(37 * n / dur) if dur else 112, n + 12), 130)
        datos = _ajustar_largo(cfg, brief, previo, objetivo - 4, 128, objetivo)
        _validar(datos, estilo)
        for k in ("combo", "cta", "formato", "modelo"):
            datos[k] = previo.get(k)
        if producto:
            _cierre_producto(datos, hist)
        return datos

    formato = formato or elegir_formato(hist)
    if formato not in FORMATOS:
        raise ValueError(f"Formato desconocido «{formato}». Opciones: " + ", ".join(FORMATOS))
    f = FORMATOS[formato]
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
        r, sv = elegir_combo(hist, formato, rubro)
        combo = f"{r}/{sv}/{formato}"
        pedido = f"Rubro: {RUBROS[r]}.\nQué mostrar: {SERVICIOS[sv]}."
    pedido += f"\nFormato narrativo ({formato}): {f['guion']}"
    tienda = bool(re.search(r"tienda online|e-?commerce", (tema or "") + (producto or ""), re.I))
    if formato == "cliente-tipo":
        pedido += ("\nEl cliente de la historia es genérico (sin nombre propio ni cifras). "
                   + ('Como es una tienda online, podés nombrar a "Todo y Más" (tienda online real de mortups).' if tienda
                      else 'No nombres a "Todo y Más" ni a "Repuestos San Isidro".'))
    cta = "producto" if producto else elegir_cta(hist)
    pedido += f"\nLlamado final (última escena): {CTAS[cta]['voz']}."
    previos = hist.ganchos(30)
    if previos:
        pedido += "\n\nGanchos ya usados (no repitas ni parafrasees ninguno):\n- " + "\n- ".join(previos)
    temas_previos = hist.temas(10)
    if temas_previos:
        pedido += ("\n\nTemas recientes: variá el ángulo, los ejemplos y las situaciones; no uses los mismos:\n- "
                   + "\n- ".join(temas_previos))

    datos = llm.chat_json(cfg, SISTEMA.format(brief=brief), pedido, temperature=1.0)
    datos = llm.chat_json(
        cfg, EDITOR.format(brief=brief), "Guion a revisar:\n" + _dump(datos), temperature=0.4
    )
    datos = _ajustar_largo(cfg, brief, datos, *RANGO_PALABRAS)
    _validar(datos, estilo)
    if producto:
        _cierre_producto(datos, hist)
    datos["combo"] = combo
    datos["modelo"] = llm.ULTIMO_MODELO[0]
    datos["cta"] = cta
    datos["formato"] = formato
    return datos


def texto_locucion(datos: dict) -> str:
    return "\n\n".join(e["texto"].strip() for e in datos["escenas"])


def _dump(d: dict) -> str:
    import json

    return json.dumps(d, ensure_ascii=False)


def _validar(d: dict, estilo: str = "stock") -> None:
    if not isinstance(d.get("escenas"), list) or len(d["escenas"]) < 3:
        raise llm.LLMError("El guion vino sin escenas suficientes.")
    for e in d["escenas"]:
        if estilo == "animado":
            e.setdefault("buscar", "")  # el estilo animado no usa clips de stock
        if not e.get("texto") or (estilo != "animado" and not e.get("buscar")):
            raise llm.LLMError("Hay una escena sin texto o sin búsqueda.")
    _acortar_gancho(d)
    d.setdefault("tema", d["escenas"][0]["texto"])
    d["gancho"] = d["escenas"][0]["texto"]
    d.setdefault("titulo", "")
    d.setdefault("caption", "")
    d.setdefault("hashtags", [])


def _acortar_gancho(d: dict, maximo: int = 12) -> None:
    """El gancho tiene que entrar en el primer segundo: si la primera escena es larga, se parte en la primera frase."""
    e = d["escenas"][0]
    if len(re.findall(r"\w+", e["texto"])) <= maximo:
        return
    frases = re.split(r"(?<=[.?!…])\s+", e["texto"].strip())
    if len(frases) > 1 and len(re.findall(r"\w+", frases[0])) <= maximo:
        corte = len(frases[0])
    else:  # una sola frase larga: se corta en la coma más cercana a la palabra 8
        palabras = list(re.finditer(r"\S+", e["texto"]))
        comas = [m.end() for m in palabras[:maximo] if m.group().endswith(",")]
        if not comas or len(palabras) <= maximo:
            return
        corte = comas[-1]
    resto = e["texto"][corte:].strip()
    if resto:
        e["texto"] = e["texto"][:corte].strip()
        d["escenas"].insert(1, {**e, "texto": resto})
