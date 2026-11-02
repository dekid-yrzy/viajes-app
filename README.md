# viajes-app

App personal para planificar viajes y rastrear precios de vuelos desde SCL. Se actualiza sola una vez al día con GitHub Actions y se publica en GitHub Pages. El diseño completo está en [docs/SPEC.md](docs/SPEC.md).

## Desarrollo

- Tests: `python -m unittest discover -s tests -v`
- Recolector: `TRAVELPAYOUTS_TOKEN=... python -m recolector`
- Vista local: `python -m http.server 8000` y abrir http://localhost:8000

## Secretos de GitHub Actions

`TRAVELPAYOUTS_TOKEN`, `SERPAPI_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_DESTINO`. En H0–H1 solo se usa `TRAVELPAYOUTS_TOKEN`.
