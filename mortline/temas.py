"""Estilos visuales del modo animado: cada uno con paleta, tipografía, fondo y subtítulos propios.

Las tipografías (Google Fonts, OFL) están en assets/fonts y se cargan desde disco: el render no pide nada a internet.
El violeta de la marca queda solo en la placa final.
"""

from __future__ import annotations


def _ass(hexa: str) -> str:
    """#RRGGBB -> &H00BBGGRR (formato de color de ASS)."""
    h = hexa.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper().replace("&H00", "&H00")


ESTILOS: dict[str, dict] = {
    "cuaderno": {
        "desc": "hoja de cuaderno rayada, tinta azul, marcador amarillo y lapicera roja, garabatos a mano",
        "display": "CaveatBrush-Regular.ttf", "body": "PatrickHand-Regular.ttf",
        "ass": dict(fuente="Caveat Brush", tam=150, negrita=0, texto="#1C2B4B", activo="#D9382F",
                    borde="#F3EDDC", grosor=5, sombra=0, max_chars=14),
    },
    "pizarra": {
        "desc": "pizarra verde con tiza blanca, amarilla y rosa, marco de madera, polvo de tiza",
        "display": "Gaegu-Bold.ttf", "body": "PatrickHand-Regular.ttf",
        "ass": dict(fuente="Gaegu", tam=125, negrita=1, texto="#F4F1E6", activo="#FFD966",
                    borde="#1F3B31", grosor=5, sombra=0, max_chars=13),
    },
    "editorial": {
        "desc": "revista: fondo claro, serif negra, filetes finos y un solo acento rojo",
        "display": "DMSerifDisplay-Regular.ttf", "body": "Poppins-Medium.ttf",
        "ass": dict(fuente="DM Serif Display", tam=120, negrita=0, texto="#121212", activo="#D7261E",
                    borde="#F2EEE3", grosor=4, sombra=0, max_chars=15),
    },
    "ticket": {
        "desc": "ticket térmico sobre papel, tipografía de máquina, líneas punteadas y total en negativo",
        "display": "CourierPrime-Bold.ttf", "body": "SpaceMono-Bold.ttf",
        "ass": dict(fuente="Courier Prime", tam=104, negrita=1, texto="#1A1A1A", activo="#C62828",
                    borde="#F8F6EF", grosor=4, sombra=0, max_chars=13),
    },
    "planilla": {
        "desc": "hoja de cálculo: grilla, encabezados A-B-C, celda seleccionada en verde",
        "display": "Poppins-SemiBold.ttf", "body": "SpaceMono-Regular.ttf",
        "ass": dict(fuente="Poppins SemiBold", tam=98, negrita=0, texto="#202124", activo="#1E8E3E",
                    borde="#FFFFFF", grosor=5, sombra=0, max_chars=15),
    },
    "neon": {
        "desc": "neón retro: noche azul oscura, cian y rosa, sol y grilla en fuga",
        "display": "Bungee-Regular.ttf", "body": "Poppins-Medium.ttf",
        "ass": dict(fuente="Bungee", tam=118, negrita=0, texto="#F3FBFF", activo="#FF3CAC",
                    borde="#06101C", grosor=6, sombra=0, max_chars=12),
    },
    "pop": {
        "desc": "pop collage: amarillo fuerte, semitono, contornos negros gruesos y pegatinas",
        "display": "LilitaOne-Regular.ttf", "body": "LilitaOne-Regular.ttf",
        "ass": dict(fuente="Lilita One", tam=130, negrita=0, texto="#FFFFFF", activo="#FF3D81",
                    borde="#000000", grosor=10, sombra=4, max_chars=15),
    },
    "minimal": {
        "desc": "minimal claro: mucho aire, sans geométrica negra y un solo azul eléctrico",
        "display": "Poppins-Bold.ttf", "body": "Poppins-Medium.ttf",
        "ass": dict(fuente="Poppins", tam=98, negrita=1, texto="#111111", activo="#2B50FF",
                    borde="#F5F4EF", grosor=4, sombra=0, max_chars=15),
    },
}
# La marca (violeta) solo se usa para la placa final y como estilo por defecto de respaldo.
ESTILOS["marca"] = {
    "desc": "respaldo: fondo violeta de la marca",
    "display": "HankenGrotesk-ExtraBold.ttf", "body": "HankenGrotesk-SemiBold.ttf",
    "ass": dict(fuente="Hanken Grotesk ExtraBold", tam=96, negrita=0, texto="#FFFFFF", activo="#8B2CFF",
                borde="#000000", grosor=7, sombra=3, max_chars=16),
}

ROTABLES = [k for k in ESTILOS if k != "marca"]

# Variables CSS de cada estilo (las usa animado/escena.html) y su lenguaje de movimiento:
#   mov = tipo de entrada (resorte, suave, borrado, escalon, parpadeo), tamaño del salto y rigidez del resorte.
VISUAL = {
    "cuaderno": dict(esc=1.2, bg="#F3EDDC", fg="#1C2B4B", mut="#5C6A8A", acc="#D9382F", onacc="#FFFFFF", hl="#1C2B4B",
                     card="#FFFDF4", cardb="#1C2B4B", cli="#E7EFFB", track="#D9D2BC",
                     rc="16px", bw="4px", sh="7px 7px 0 #1C2B4B", df="CaveatX", bf="PatrickX", dpeso="400",
                     mov=dict(tipo="resorte", k=150, c=13, y=50, s=.85, r=-3, giro=1.1)),
    "pizarra": dict(esc=1.15, bg="#24443A", fg="#F4F1E6", mut="#B9CFC3", acc="#FF9EBB", onacc="#1F3B31", hl="#FFD966",
                    card="rgba(244,241,230,.05)", cardb="rgba(244,241,230,.75)", cli="rgba(244,241,230,.12)", track="rgba(244,241,230,.2)",
                    rc="20px", bw="4px", sh="none", df="GaeguX", bf="PatrickX", dpeso="700",
                    mov=dict(tipo="borrado", y=0, giro=.6)),
    "editorial": dict(esc=1.0, bg="#F2EEE3", fg="#121212", mut="#5B574F", acc="#D7261E", onacc="#FFFFFF", hl="#D7261E",
                      card="rgba(18,18,18,.0)", cardb="#121212", cli="#E6E1D3", track="#D8D2C2",
                      rc="0px", bw="2px", sh="none", df="DMSerifX", bf="PoppinsM", dpeso="400",
                      mov=dict(tipo="suave", y=34, giro=0)),
    "ticket": dict(esc=0.8, bg="#F8F6EF", fg="#1A1A1A", mut="#6B6B66", acc="#1A1A1A", onacc="#F8F6EF", hl="#1A1A1A",
                   card="rgba(0,0,0,0)", cardb="#1A1A1A", cli="#ECE9DE", track="#D9D6CA",
                   rc="0px", bw="3px", sh="none", df="CourierX", bf="SpaceX", dpeso="700",
                   mov=dict(tipo="escalon", y=60, giro=0)),
    "planilla": dict(esc=0.95, bg="#FFFFFF", fg="#202124", mut="#5F6368", acc="#1E8E3E", onacc="#FFFFFF", hl="#1E8E3E",
                     card="#FFFFFF", cardb="#C6C9CE", cli="#F1F3F4", track="#E3E5E8",
                     rc="8px", bw="2px", sh="0 6px 18px rgba(32,33,36,.14)", df="PoppinsS", bf="SpaceX", dpeso="600",
                     mov=dict(tipo="borrado", y=0, giro=0)),
    "neon": dict(esc=0.72, bg="#070B1C", fg="#F3FBFF", mut="#7FD9F0", acc="#00E5FF", onacc="#06101C", hl="#FF3CAC",
                 card="rgba(0,229,255,.06)", cardb="#00E5FF", cli="rgba(0,229,255,.12)", track="rgba(0,229,255,.18)",
                 rc="14px", bw="3px", sh="0 0 28px rgba(0,229,255,.55)", df="BungeeX", bf="PoppinsM", dpeso="400",
                 mov=dict(tipo="parpadeo", y=0, giro=0)),
    "pop": dict(esc=1.0, bg="#FFD500", fg="#111111", mut="#3A3A3A", acc="#FF3D81", onacc="#FFFFFF", hl="#FF3D81",
                card="#FFFFFF", cardb="#111111", cli="#FFFFFF", track="#111111",
                rc="22px", bw="6px", sh="10px 10px 0 #111111", df="LilitaX", bf="LilitaX", dpeso="400",
                mov=dict(tipo="resorte", k=230, c=9, y=90, s=.4, r=-9, giro=1.5)),
    "minimal": dict(esc=0.95, bg="#F5F4EF", fg="#111111", mut="#77756E", acc="#2B50FF", onacc="#FFFFFF", hl="#2B50FF",
                    card="#FFFFFF", cardb="#E3E1DA", cli="#ECEAE3", track="#E3E1DA",
                    rc="36px", bw="2px", sh="0 18px 50px rgba(17,17,17,.08)", df="PoppinsB", bf="PoppinsM", dpeso="700",
                    mov=dict(tipo="suave", y=0, x=70, giro=0)),
}
# Familias CSS -> archivo de fuente (todas OFL, en assets/fonts).
FUENTES = {
    "CaveatX": "CaveatBrush-Regular.ttf", "PatrickX": "PatrickHand-Regular.ttf", "GaeguX": "Gaegu-Bold.ttf",
    "DMSerifX": "DMSerifDisplay-Regular.ttf", "PoppinsM": "Poppins-Medium.ttf", "PoppinsS": "Poppins-SemiBold.ttf",
    "PoppinsB": "Poppins-Bold.ttf", "CourierX": "CourierPrime-Bold.ttf", "SpaceX": "SpaceMono-Bold.ttf",
    "BungeeX": "Bungee-Regular.ttf", "LilitaX": "LilitaOne-Regular.ttf",
    "HankenX": "HankenGrotesk-ExtraBold.ttf",
}


def elegir(hist, forzado: str | None = None, ultimos: int = 4) -> str:
    """Estilo visual que no se repita en los últimos `ultimos` reels (o el que se pidió con --estilo-visual)."""
    import random

    if forzado:
        return forzado
    usados = [r.get("estilo_visual") for r in hist.reels[-ultimos:]]
    libres = [e for e in ROTABLES if e not in usados]
    return random.choice(libres or ROTABLES)


def estilo_ass(nombre: str) -> str:
    a = ESTILOS[nombre]["ass"]
    return (f"Style: Sub,{a['fuente']},{a['tam']},{_ass(a['texto'])},{_ass(a['texto'])},{_ass(a['borde'])},"
            f"&H80000000,{-1 if a['negrita'] else 0},0,0,0,100,100,0,0,1,{a['grosor']},{a['sombra']},5,60,130,0,1")
