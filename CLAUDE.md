# mortline
Pipeline de reels para mortups (Python 3.11+, uv, ffmpeg). Comando: `mortline`. Paquete en `mortline/`.
- No hay tests: el hook Stop solo compila (`compileall`). Para verificar de verdad, generar un reel y mirar cuadros (ffmpeg -> PNG).
- Guion vía FreeLLMAPI (app de escritorio, puerto 31416; abrir con `freellmapi-app`), voz GGNarrator. Sin claves en el repo.
- Estilo por defecto `animado`: `animado.py` + `animado/escena.html` (Playwright/Chromium, cuadro a cuadro) y `escenas.py`
  (JSON de escenas del LLM, validación, fallback). `--estilo stock` usa clips libres como antes.
- Al tocar `escena.html`: medir texto solo con el elemento ya en el DOM y visible (si no, mide 0); zona de contenido y 1420 px
  de subtítulos no se pisan (contenido entre y=450 y y=1250 y x=50..950, subtítulos en y=1420, zona segura: no usar los últimos ~380 px ni los 120 px de la derecha).
- Estilos visuales en `temas.py` (variables CSS + movimiento + subtítulos ASS) y su fondo/tratamiento en `escena.html` (`FONDOS`, bloques `body.t-<estilo>`).
  Formatos narrativos en `guion.FORMATOS` (estructura + escenas sugeridas). Ambos rotan sin repetir los últimos 4 (`historial.json`: `estilo_visual`, `formato`).
- Voz mínima 30 s (GGNarrator ~3,2 palabras/s; guion de 100–120 palabras); si no llega se reescribe el guion hasta 2 veces y si no, error.
- Carpetas: final `~/Downloads/job/reels/<Título>/` (mp4, caption, portada); trabajo `data/trabajo/<fecha>_<slug>/` (guion, voz, créditos; `--rehacer` lo busca por título).
- Violeta de marca solo en la placa final; fuentes OFL en `assets/fonts/`. Para ver los estilos sin generar un reel: `animado.cuadros(...)`.
