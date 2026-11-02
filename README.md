# viajes-app

App personal para planificar viajes y rastrear precios de vuelos desde SCL. Se actualiza sola una vez al día con GitHub Actions y se publica en GitHub Pages. El diseño completo está en [docs/SPEC.md](docs/SPEC.md).

## Desarrollo

- Dependencias de runtime: `pip install -r requirements.txt` (solo fast-flights; los tests no la necesitan)
- Tests: `python -m unittest discover -s tests -v` y `node --test "tests/js/*.test.js"` (frontend, sin dependencias)
- Frontend: `index.html` + `app.js` (vistas) y `js/` (lógica pura: estadística, datos, formato, gráfico)
- Recolector: `TRAVELPAYOUTS_TOKEN=... SERPAPI_KEY=... python -m recolector` (`DESACTIVAR_FAST_FLIGHTS=1` apaga el scraping de Google Flights)
- Vista local: `python -m http.server 8000` y abrir http://localhost:8000

## Secretos de GitHub Actions

`TRAVELPAYOUTS_TOKEN`, `SERPAPI_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_DESTINO`. Hoy se usan todos. Si faltan los de Telegram o email, ese canal se salta y las alertas quedan solo en la app.

## Configurar alertas

Cada secreto se carga con `gh secret set <NOMBRE> --repo dekid-yrzy/viajes-app` (pegando el valor cuando lo pida).

**Telegram**
1. En Telegram, abre @BotFather, envía `/newbot` y sigue los pasos. Copia el token que te entrega → `TELEGRAM_BOT_TOKEN`.
2. Abre el chat con tu bot nuevo y envíale cualquier mensaje.
3. Abre `https://api.telegram.org/bot<TOKEN>/getUpdates` en el navegador y copia el número de `"chat":{"id": ...}` → `TELEGRAM_CHAT_ID`.

**Email (Gmail)**
1. Activa la verificación en dos pasos en tu cuenta de Google.
2. Crea una contraseña de aplicación en https://myaccount.google.com/apppasswords.
3. Carga `SMTP_USER` (tu Gmail), `SMTP_PASSWORD` (la contraseña de aplicación de 16 letras, sin espacios) y `EMAIL_DESTINO` (adonde llegan las alertas).
