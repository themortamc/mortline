# mortline
Pipeline de reels para mortups (Python 3.11+, uv, ffmpeg). Comando: `mortline`. Paquete en `mortline/`.
- No hay tests: el hook Stop solo compila (`compileall`). Para verificar de verdad, generar un reel y mirar cuadros (ffmpeg -> PNG).
- Guion vía FreeLLMAPI (app de escritorio, puerto 31416; abrir con `freellmapi-app`), voz GGNarrator. Sin claves en el repo.
- Estilo por defecto `animado`: `animado.py` + `animado/escena.html` (Playwright/Chromium, cuadro a cuadro) y `escenas.py`
  (JSON de escenas del LLM, validación, fallback). `--estilo stock` usa clips libres como antes.
- Al tocar `escena.html`: medir texto solo con el elemento ya en el DOM y visible (si no, mide 0); zona de contenido y 1420 px
  de subtítulos no se pisan (contenido entre y=450 y y=1250, subtítulos en y=1420, zona segura: no usar los últimos ~380 px).
