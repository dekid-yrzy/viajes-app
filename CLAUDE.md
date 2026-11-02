# viajes-app

App personal de planificación de viajes y tracking de precios de vuelos. Uso individual, no es un producto comercial.

## Idioma y valores por defecto
- UI y documentación en español.
- Moneda principal: CLP, con conversión a USD y EUR.
- Aeropuerto de origen por defecto: SCL (configurable).

## Restricción central
La app debe actualizarse sola, SIN depender de Claude ni de ninguna suscripción. Cero llamadas a LLM en runtime.

## Stack
- Python solo para recolección de datos.
- Frontend: HTML/CSS/JS vanilla, sin build step.
- Datos: archivos JSON versionados en el repo.
- Hosting: GitHub Pages.
- Actualización periódica: cron en GitHub Actions.

## Dependencias
Mínimas (ponytail): primero stdlib de Python y APIs nativas del navegador. Agregar una dependencia solo si ahorra mucho más que unas pocas líneas.

## Estilo
- Caveman solo para las respuestas en chat.
- Código, commits, comentarios y textos de UI se escriben en prosa normal.

## Flujo de trabajo
Usar superpowers en cada módulo: brainstorming, plan, TDD donde aporte, review.
