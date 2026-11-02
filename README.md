# viajes-app

App personal para planificar viajes y rastrear precios de vuelos desde SCL. Se actualiza sola una vez al día con GitHub Actions y se publica en GitHub Pages. El diseño completo está en [docs/SPEC.md](docs/SPEC.md).

## Desarrollo

- Dependencias de runtime: `pip install -r requirements.txt` (solo fast-flights; los tests no la necesitan)
- Tests: `python -m unittest discover -s tests -v` y `node --test "tests/js/*.test.js"` (frontend, sin dependencias)
- Frontend: `index.html` + `app.js` (vistas) y `js/` (lógica pura: estadística, datos, formato, gráfico)
- Recolector: `TRAVELPAYOUTS_TOKEN=... SERPAPI_KEY=... python -m recolector` (`DESACTIVAR_FAST_FLIGHTS=1` apaga el scraping de Google Flights)
- Vista local: `python -m http.server 8000` y abrir http://localhost:8000

## Secretos de GitHub Actions

`TRAVELPAYOUTS_TOKEN`, `SERPAPI_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_DESTINO`. Hoy se usan `TRAVELPAYOUTS_TOKEN` y `SERPAPI_KEY`.
