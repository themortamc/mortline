"""Escenas visuales del estilo animado: el LLM las diseña, se validan y se ajustan al tiempo de la voz."""

from __future__ import annotations

import json
import re

from . import animado, llm
from .config import Config

PLANTILLAS = {
    # plantilla: (mínimo de textos, máximo de textos, icono por defecto)
    "titular": (1, 3, "sparkles"),   # texto grande con entrada por palabra + icono arriba
    "pasos": (2, 3, "list-checks"),  # lista numerada 1-2-3
    "flujo": (2, 3, "arrow-right"),  # cajas unidas por flechas (A -> B -> C), la última destacada
    "dato": (2, 2, "clock"),         # número grande que sube [valor, etiqueta]
    "chat": (2, 4, "message-circle"),  # celular con conversación (cliente / negocio)
    "grafico": (3, 5, "trending-up"),  # barras que crecen [título, etiqueta1..4]
}
MAX_CHARS = {"titular": 28, "pasos": 26, "flujo": 22, "dato": 28, "chat": 34, "grafico": 22}
ALIAS = {"titulo": "titular", "texto": "titular", "paso": "pasos", "dato": "dato", "datos": "dato", "numero": "dato",
         "número": "dato", "flujos": "flujo", "graficos": "grafico", "gráfico": "grafico", "barras": "grafico",
         "whatsapp": "chat", "conversacion": "chat"}
MAX_SEG = 3.3    # un corte como mucho cada ~3 s
MIN_SEG = 0.9

PROMPT = """Sos director de motion graphics de reels verticales explicativos (fondo violeta oscuro, texto grande
blanco con la palabra clave resaltada, íconos y mini escenas de interfaz). Recibís el guion hablado con cada
palabra numerada y el segundo en que se dice. Diseñás los cortes visuales que acompañan a la voz.

Plantillas disponibles (campo "plantilla"):
- titular: texto grande. "textos": 1 a 3 líneas cortas (máx 28 caracteres c/u). "icono" obligatorio. Es la base del gancho y del remate.
- pasos: lista numerada. "textos": 2 o 3 pasos de máx 4 palabras. Para procesos ("elige, se arma, te llega").
- flujo: cajas con flechas. "textos": 2 o 3 cajas de máx 3 palabras (ej. "Tu negocio", "Catálogo web", "Tu plata"). Opcional "iconos": un icono por caja. La última caja es la que se destaca. Para transformaciones, antes -> después, causa -> efecto.
- dato: número grande. "textos": [valor, etiqueta]. El valor es corto ("24 a 72 hs", "30.000", "0 comisiones"), la etiqueta máx 5 palabras. SOLO con cifras que están en el brief o en el guion; jamás inventes números.
- chat: conversación de WhatsApp. "textos": 2 a 4 mensajes alternados (1.º cliente, 2.º el negocio, etc.), máx 6 palabras c/u. El último mensaje (si es del negocio) se destaca.
- grafico: barras que suben. "textos": [título corto, etiqueta1, etiqueta2, (etiqueta3), (etiqueta4)], etiquetas de 1 o 2 palabras (ej. días, pasos, etapas). Sin cifras ni porcentajes. No lo uses para prometer resultados.

Reglas:
- Cada escena tiene "desde": el NÚMERO de la primera palabra del guion con la que arranca. La primera escena arranca en 0.
- Entre 7 y 10 escenas para ~20 s. Cada escena dura entre 1,5 y 3 s (mirá los segundos de cada palabra): NINGUNA puede durar más de 3 s,
  o sea que el "desde" de la escena siguiente tiene que estar a menos de 3 s del de la actual. Una frase larga se reparte en 2 escenas.
- Ritmo por beats: gancho (titular, ya en el primer segundo) -> problema -> giro -> solución mortups -> cierre. Variá las plantillas: no repitas la misma dos veces seguidas y usá al menos 4 distintas.
- La escena del remate (la frase justo después de una pausa "...") es una escena propia, limpia y fuerte: un titular corto.
- Los textos en pantalla resumen o refuerzan lo que se dice, no copian la frase entera. Español rioplatense con voseo, ortografía perfecta con tildes, sin emojis, sin números de teléfono.
- "resaltar": lista de 1 o 2 palabras (exactas, tal como están en "textos") para pintar en amarillo.
- "icono": uno de esta lista exacta: {iconos}

Respondé SOLO con este JSON:
{{"escenas": [{{"desde": 0, "plantilla": "titular", "textos": ["..."], "icono": "store", "resaltar": ["..."]}}]}}"""


class EscenasError(ValueError):
    pass


def _validar(d, palabras, dur_voz: float) -> list[dict]:
    try:
        return _validar_esquema(d, palabras, dur_voz)
    except (TypeError, AttributeError, KeyError) as exc:  # el modelo devolvió algo con otra forma
        raise EscenasError(f"formato inesperado ({exc})")


def _validar_esquema(d, palabras, dur_voz: float) -> list[dict]:
    """Valida el JSON del modelo contra el esquema y los tiempos. Corrige lo menor; falla en lo grave."""
    iconos = set(animado.iconos_disponibles())
    esc = d.get("escenas") if isinstance(d, dict) else None
    if not isinstance(esc, list) or not 4 <= len(esc) <= 12:
        raise EscenasError("tiene que haber entre 4 y 12 escenas")
    out, previo = [], -1
    for i, e in enumerate(esc):
        if not isinstance(e, dict):
            raise EscenasError(f"la escena {i} no es un objeto")
        pl = ALIAS.get(str(e.get("plantilla", "")).lower().strip(), str(e.get("plantilla", "")).lower().strip())
        textos = e.get("textos")
        if isinstance(textos, str):
            textos = [textos]
        if not isinstance(textos, list) or not [t for t in textos if isinstance(t, str) and t.strip()]:
            raise EscenasError(f"escena {i}: «textos» tiene que ser una lista de textos")
        textos = [t.strip() for t in textos if isinstance(t, str) and t.strip()]
        # Fallas menores (plantilla rara, pocos o muchos textos): la escena se simplifica a titular, no se descarta todo.
        if pl not in PLANTILLAS or len(textos) < PLANTILLAS[pl][0]:
            pl = "titular"
        lo, hi, defecto = PLANTILLAS[pl]
        textos = textos[:hi]
        desde = e.get("desde")
        if not isinstance(desde, int) or isinstance(desde, bool) or not 0 <= desde < len(palabras):
            raise EscenasError(f"escena {i}: «desde» tiene que ser un número de palabra entre 0 y {len(palabras) - 1}")
        if desde <= previo:
            raise EscenasError(f"escena {i}: «desde» tiene que ser mayor que el de la anterior")
        previo = desde
        ic = e.get("icono")
        ic = ic[0] if isinstance(ic, list) and ic else ic
        icono = ic if isinstance(ic, str) and ic in iconos else defecto
        resaltar = e.get("resaltar") or []
        if isinstance(resaltar, str):
            resaltar = [resaltar]
        lista_iconos = [x for x in (e.get("iconos") or []) if isinstance(x, str) and x in iconos] if pl == "flujo" else []
        out.append({"desde": desde, "plantilla": pl, "textos": textos, "icono": icono,
                    "iconos": lista_iconos, "resaltar": [str(r) for r in resaltar][:3]})
    if out[0]["desde"] != 0:
        out[0]["desde"] = 0
    return _partir(out, palabras, dur_voz)


def tiempos(esc: list[dict], palabras, dur_voz: float) -> list[tuple[float, float]]:
    ini = [0.0 if i == 0 else max(0.0, palabras[e["desde"]].inicio - 0.04) for i, e in enumerate(esc)]
    return [(ini[i], ini[i + 1] if i + 1 < len(esc) else dur_voz) for i in range(len(esc))]


def _partir(esc: list[dict], palabras, dur_voz: float) -> list[dict]:
    """Una escena que dura más de ~3 s se corta: la plantilla queda al principio y el resto de la
    frase sigue como titular simple (así nunca hay una imagen quieta de más de 3 s)."""
    ciclo = ["zap", "search", "check", "store", "wallet", "smartphone"]
    out, k = [], 0
    for i, e in enumerate(esc):
        out.append(e)
        ini_i = esc[i]["desde"]
        fin_i = esc[i + 1]["desde"] if i + 1 < len(esc) else len(palabras)
        t0 = palabras[ini_i].inicio
        t1 = palabras[fin_i].inicio if fin_i < len(palabras) else dur_voz
        n = int((t1 - t0) / MAX_SEG) + (1 if (t1 - t0) % MAX_SEG > 0.4 else 0)
        if t1 - t0 <= MAX_SEG + 0.2 or n < 2:
            continue
        cortes = []
        for j in range(1, n):
            objetivo = t0 + (t1 - t0) * j / n
            idx = min(range(ini_i + 1, fin_i), key=lambda w: abs(palabras[w].inicio - objetivo), default=None)
            if idx is not None and (not cortes or idx > cortes[-1]):
                cortes.append(idx)
        for c, idx in enumerate(cortes):
            hasta = cortes[c + 1] if c + 1 < len(cortes) else fin_i
            frase = [p.texto.strip(",;.…") for p in palabras[idx:hasta]][:6]
            mitad = (len(frase) + 1) // 2 if len(frase) > 3 else len(frase)
            lineas = [" ".join(frase[:mitad]), " ".join(frase[mitad:])] if mitad < len(frase) else [" ".join(frase)]
            out.append({"desde": idx, "plantilla": "titular", "textos": lineas, "icono": ciclo[k % len(ciclo)],
                        "iconos": [], "resaltar": []})
            k += 1
    return out


def _guion_numerado(palabras) -> str:
    return "\n".join(f"{i}\t{p.inicio:.1f} s\t{p.texto}" for i, p in enumerate(palabras))


def _fallback(palabras) -> list[dict]:
    """Escenas simples de texto (titular + ícono) cortadas por frases, cada ≤3 s. Nunca falla."""
    ciclo = ["message-circle", "search", "zap", "store", "smartphone", "check", "clock", "wallet"]
    esc, ini = [], 0
    for i, p in enumerate(palabras):
        acumulado = p.fin - palabras[ini].inicio
        fin_frase = bool(re.search(r"[.?!…:]$", p.texto)) and acumulado > 1.2
        if i - ini + 1 >= 6 or acumulado > 2.4 or fin_frase or i == len(palabras) - 1:
            frase = [x.texto.strip(",;.") for x in palabras[ini:i + 1]]
            mitad = (len(frase) + 1) // 2 if len(frase) > 3 else len(frase)
            lineas = [" ".join(frase[:mitad]), " ".join(frase[mitad:])] if mitad < len(frase) else [" ".join(frase)]
            esc.append({"desde": ini, "plantilla": "titular", "textos": lineas, "icono": ciclo[len(esc) % len(ciclo)],
                        "iconos": [], "resaltar": []})
            ini = i + 1
    return esc


def generar(cfg: Config, datos: dict, palabras, dur_voz: float) -> tuple[list[dict], list[tuple[float, float]], str]:
    """Devuelve (escenas, tramos[(ini, fin)], origen). origen: 'llm' o 'fallback'."""
    brief = cfg.marca.read_text(encoding="utf-8")
    sistema = PROMPT.format(iconos=", ".join(animado.iconos_disponibles())) + "\n\nBrief de la marca:\n" + brief
    usuario = ("Guion (número, segundo, palabra):\n" + _guion_numerado(palabras) +
               f"\n\nDuración de la voz: {dur_voz:.1f} s. Título del reel: {datos.get('titulo', '')}")
    error = ""
    for intento in range(2):
        pedido = usuario if not error else (
            usuario + f"\n\nTu respuesta anterior no pasó la validación: {error}. Corregila y devolvé el JSON completo.")
        try:
            esc = _validar(llm.chat_json(cfg, sistema, pedido, temperature=0.7), palabras, dur_voz)
            return esc, tiempos(esc, palabras, dur_voz), "llm"
        except EscenasError as exc:
            error = str(exc)
            print(f"   (escenas: {error}; {'reintento' if intento == 0 else 'uso escenas simples'})")
        except llm.LLMError as exc:
            error = str(exc)
            break
    esc = _fallback(palabras)
    return esc, tiempos(esc, palabras, dur_voz), "fallback"


def a_json(esc: list[dict]) -> str:
    return json.dumps(esc, ensure_ascii=False)
