# SPEC — viajes-app

Estado: borrador para aprobación · Fecha: 2026-11-02

## 1. Intención

App web personal, de un solo usuario, que responde una pregunta por sobre todas: **¿es buen momento para comprar este vuelo?** Para responderla, guarda cada día el precio de un puñado de rutas (1 a 5 activas), lo compara con su propio histórico y avisa cuando aparece una oportunidad.

En segundo plano, ayuda a abaratar el costo total (aeropuertos alternativos, combinaciones con self-transfer, fechas flexibles) y a revisar el itinerario (conexiones, visas de tránsito, exportación a calendario).

La app debe funcionar sola, indefinidamente, sin Claude, sin LLM y sin suscripciones de pago.

### Perfil del usuario (decidido en la entrevista)

| Tema | Decisión |
|---|---|
| Origen | SCL por defecto, configurable |
| Destinos típicos | Europa y Asia/Oceanía: vuelos largos con escalas |
| Escalas | Solo conexiones para abaratar. El destino es uno (no hay estancias en ciudades intermedias) |
| Flexibilidad de fechas | Varía por viaje. Hay que soportar fecha fija, fecha ±N días y mes completo |
| Riesgo | Moderado. Se acepta self-transfer (billetes separados) con conexión holgada. **No** se acepta hidden-city |
| Equipaje | Se configura por viaje |
| Pasaportes | Chileno y alemán. La app elige el más conveniente para cada tránsito |
| Millas / alianzas | Ninguna. Solo cuenta el precio en efectivo |
| Presupuesto | Umbral manual opcional en CLP más una señal automática por percentil histórico |
| Alertas | Email, Telegram y dentro de la app |
| Dispositivo | Celular y computador por igual: responsive y PWA instalable |
| Frecuencia de captura | 1 vez al día |
| Privacidad | Repo público, sin datos personales en el repo |
| Edición de viajes | Desde la propia app, con un token personal de GitHub guardado solo en el navegador |
| Moneda | CLP principal, con conversión a USD y EUR |
| Idioma | Español en la UI y en la documentación |

## 2. Objetivos, no-objetivos y anti-objetivos

**Objetivos**
1. Histórico diario de precios por viaje rastreado, con percentil y tendencia.
2. Alertas confiables, sin spam, por los tres canales.
3. Costo total real (tarifa + equipaje + traslados + extras de self-transfer) en CLP, USD y EUR.
4. Funcionar sin intervención durante meses.

**No-objetivos**
- Comprar o reservar pasajes. La app solo enlaza al sitio de compra.
- Multiusuario, cuentas o login propio.
- Millas, puntos o tarifas premio.
- Hoteles, autos o actividades.
- Predicción con machine learning. Se usa estadística simple y explicable.

**Anti-objetivos** (cosas que la harían un fracaso aunque funcione)
- Que dependa de que Claude o una persona la ejecute para actualizarse.
- Que se rompa en silencio. Si una fuente falla, la app debe mostrarlo.
- Que mande alertas repetidas o irrelevantes hasta que el usuario deje de mirarlas.
- Que exponga datos personales (pasaportes, tokens) en el repo público.
- Que requiera build step, framework frontend o servidor propio.

## 3. Casos de uso priorizados

**P1: núcleo, "saber cuándo comprar"**
1. **Rastrear un viaje.** Se define origen, destino, modo de fechas (fija, ±N días o mes), ida o ida y vuelta, duración de la estadía, pasajeros, equipaje y umbral opcional en CLP.
2. **Histórico y percentil.** Gráfico del precio mínimo diario observado, con bandas p25/p50/p75 y una etiqueta "bueno / normal / caro" respecto al histórico propio.
3. **Alertas.** Comparan siempre el costo total real para todos los pasajeros (ver 4.4). Hay tres disparadores: (a) el costo baja del umbral manual; (b) cae ≥X% respecto a la mediana de los últimos 7 días (X=10% por defecto); (c) aparece un nuevo mínimo histórico con al menos 14 observaciones.
4. **Calendario de precios.** Para viajes con fechas flexibles, una grilla con el precio por fecha de salida (y de regreso cuando aplica), coloreada por percentil.
5. **Conversión de moneda.** CLP, USD y EUR con el tipo de cambio del día de la captura.

**P2: abaratar el costo total**

6. **Aeropuertos alternativos.** Se comparan los aeropuertos cercanos al destino (y al origen, si se configura) dentro de un radio en km o de una lista manual.
7. **Combinaciones con self-transfer.** Se arma origen→hub + hub→destino con billetes separados por hubs configurables (por ejemplo GRU, EZE, LIM, BOG, PTY, MAD, LIS, IST, DOH, DXB). Solo se muestran si la conexión mínima es holgada (≥4 h por defecto, ≥6 h si hay equipaje facturado) y si el ahorro supera un margen de riesgo configurable.
8. **Costo total real.** Tarifa + equipaje (costo estimado por viaje que ingresa el usuario) + traslados (monto manual) + recargo de self-transfer (segundo equipaje, posible hotel de conexión).

**P3: planificar el itinerario**

9. **Vista de itinerario.** Tramos, tiempos de conexión, cambio de aeropuerto y vuelos nocturnos, con advertencias visibles.
10. **Checklist de visas y tránsito.** Para cada país de tránsito y destino indica qué se necesita con cada pasaporte y cuál conviene. Lleva siempre el aviso "verifica en la fuente oficial".
11. **Exportar a `.ics`.** El itinerario elegido se exporta a calendario, generado en el navegador.

**P4: extras**

12. **Ofertas y tarifas de error.** Se leen feeds RSS públicos de sitios de ofertas y se filtran por origen SCL o por los destinos rastreados. Es opcional y depende de que existan feeds viables (ver riesgos).
13. **Panel de salud.** Muestra la última captura exitosa por fuente, la cuota de SerpApi usada este mes y los errores recientes.

## 4. Arquitectura

```
GitHub Actions (cron diario)
  └─ recolector Python
       ├─ lee config/viajes.json y config/ajustes.json
       ├─ consulta fuentes de precios y tipos de cambio
       ├─ escribe data/*.json
       ├─ evalúa alertas → Telegram / email / data/alertas.json
       └─ git commit + push
GitHub Pages (sirve la raíz del repo)
  └─ frontend HTML/CSS/JS vanilla
       ├─ fetch de data/*.json (mismo origen)
       ├─ cálculos de presentación (percentiles, calendario, costo total)
       └─ edición de viajes → API REST de GitHub con token del usuario
```

### 4.1 Recolector (Python)

- Python 3.12 en Actions. Se usa stdlib (`urllib`, `json`, `smtplib`, `statistics`) en todo salvo la fuente `fast-flights`, que es la única dependencia externa. Va aislada en su propio módulo y si falla al importarse no tumba el resto.
- Hay un módulo por fuente con una interfaz común: recibe una consulta y devuelve una lista de ofertas normalizadas o un error tipado.
- **Estrategia de fuentes por viaje y por día:**
  1. **Travelpayouts Data API** (base). Calendario del mes o de la ventana de fechas en una llamada. Alimenta el calendario y el precio mínimo diario.
  2. **SerpApi Google Flights** (confirmación). Una consulta diaria por viaje, sobre la mejor fecha que encontró el paso 1. Tiene un presupuesto mensual duro (por defecto 200 de las ~250 gratis) y se reparte entre los viajes activos.
  3. **fast-flights** (respaldo). Solo corre si SerpApi falló o se agotó su cuota. Máximo 1 consulta por viaje al día.
  - Cada observación guarda su fuente. Los percentiles se calculan **por fuente** para no mezclar precios cacheados con precios en vivo. La etiqueta principal usa la fuente "en vivo" (SerpApi o fast-flights) si tiene ≥14 observaciones; si no, usa Travelpayouts.
- **Tipos de cambio:** mindicador.cl (dólar y euro en CLP). Si falla, se usa open.er-api.com (gratis, sin clave; incluye CLP; Frankfurter/BCE no publica CLP). Los montos se guardan en la moneda original y además en CLP convertido con el tipo de cambio del día.
- **Alertas:** se evalúan después de guardar. Para evitar repeticiones, la misma alerta (viaje + tipo) no se repite antes de 3 días salvo que el precio baje otro ≥5%.
- **Self-transfer y aeropuertos alternativos:** se buscan tramos solo-ida en Travelpayouts, que es barato en cuota. Por defecto quedan fuera de SerpApi y fast-flights.
- **Concurrencia:** el workflow usa `concurrency` para que no haya dos corridas a la vez. Antes del push hace `git pull --rebase`, porque la app web también puede commitear `config/viajes.json`.

### 4.2 Frontend

- HTML, CSS y JS vanilla con ES modules, sin build step. Los gráficos se hacen en SVG generado a mano, sin librería.
- Vistas: **Inicio** (viajes con su etiqueta bueno/normal/caro y el último precio), **Detalle de viaje** (histórico, calendario, alternativas, costo total), **Itinerario** (tramos, conexiones, visas, .ics), **Alertas**, **Ajustes** (pasaportes, token, umbrales por defecto) y **Salud**.
- **Datos personales solo en `localStorage`:** pasaportes y token de GitHub. Nunca se envían a ningún host salvo `api.github.com` (el token).
- **Edición:** el formulario de viaje hace un `PUT /repos/{owner}/{repo}/contents/config/viajes.json` con el SHA vigente. Si hay conflicto, recarga y pide reintentar. El token es fine-grained, con permiso solo para este repo y solo `contents:write`.
- **Seguridad:** CSP estricta (`script-src 'self'`) y cero scripts de terceros, para que un XSS no pueda robar el token. Todo dato de fuentes externas se inserta como texto, nunca como HTML.
- **PWA:** `manifest.json` y un service worker vanilla. El app shell va con cache-first y `data/*.json` con network-first y fallback al caché. Muestra "datos de hace N horas" cuando está offline.

### 4.3 Esquema de datos

Todos los archivos son JSON UTF-8 con fechas ISO 8601. Los montos van en enteros para CLP y en decimales con 2 cifras para USD y EUR.

**`config/ajustes.json`** (público)
```json
{
  "origen_defecto": "SCL",
  "hubs_self_transfer": ["GRU", "EZE", "LIM", "BOG", "PTY", "MAD", "LIS", "IST", "DOH", "DXB"],
  "conexion_min_horas": 4,
  "conexion_min_horas_con_maleta": 6,
  "margen_riesgo_self_transfer_clp": 80000,
  "caida_pct_alerta": 10,
  "min_observaciones_percentil": 14,
  "serpapi_presupuesto_mensual": 200,
  "radio_aeropuertos_km": 150
}
```

**`config/viajes.json`** (público; lo edita la app)
```json
{
  "viajes": [{
    "id": "scl-fra-2027-03",
    "activo": true,
    "origen": "SCL",
    "destino": "FRA",
    "aeropuertos_alternativos": ["MUC", "CDG", "AMS"],
    "tipo": "ida_vuelta",
    "fechas": {"modo": "mes", "mes": "2027-03"},
    "estadia_dias": [14, 21],
    "pasajeros": 1,
    "equipaje": {"facturadas": 1, "costo_estimado_clp": 60000},
    "traslados_clp": 0,
    "umbral_clp": 950000,
    "permite_self_transfer": true
  }]
}
```
`fechas.modo` puede ser `"fija"` (`{"salida": "2027-03-10", "regreso": "2027-03-28"}`), `"flexible"` (fechas + `"margen_dias": 3`) o `"mes"`.

**`data/precios/<viaje_id>/<AAAA-MM>.json`** (un archivo por viaje y mes de captura, para que los archivos no crezcan sin límite)
```json
{
  "viaje_id": "scl-fra-2027-03",
  "observaciones": [{
    "capturado": "2026-11-02T11:05:00Z",
    "fuente": "travelpayouts",
    "salida": "2027-03-08",
    "regreso": "2027-03-24",
    "origen": "SCL",
    "destino": "FRA",
    "precio": {"monto": 1043.20, "moneda": "USD", "clp": 987000},
    "escalas": 1,
    "duracion_min": 1080,
    "aerolineas": ["LA", "LH"],
    "self_transfer": false,
    "tramos": [],
    "enlace": "https://..."
  }]
}
```

**`data/calendario/<viaje_id>.json`**: la última grilla de fecha a precio (se sobrescribe en cada corrida).

**`data/tipos_cambio.json`**: `{"AAAA-MM-DD": {"USD": 945.3, "EUR": 1021.8}}`, acumulado.

**`data/alertas.json`**: lista de alertas emitidas con `id`, `viaje_id`, `tipo` (`umbral`, `caida_pct` o `minimo_historico`), `precio_clp`, `referencia_clp`, `fecha` y `canales_enviados`.

**`data/estado.json`**: última corrida, resultado por fuente (`ok`, `error`, `cuota_agotada`), uso de SerpApi en el mes y lista de errores recientes.

**`data/aeropuertos.json`**: subconjunto estático de OurAirports (dominio público) con código IATA, nombre, ciudad, país y coordenadas, solo aeropuertos con servicio regular.

**`data/visas.json`**: requisitos de visa por pasaporte (CL y DE) y país, generado de un dataset abierto. La información sobre tránsito específico, que no existe en fuentes gratuitas, va en un campo `notas_transito` editable a mano.

### 4.4 Definiciones de cálculo

- **Número de comparación.** El umbral, las alertas y la etiqueta bueno/normal/caro se comparan siempre contra el **costo total real del viaje para todos los pasajeros**. Ese costo es la tarifa total (todos los pasajeros) + equipaje + traslados + recargo self-transfer si aplica. *(Decisión del usuario.)*
- **Qué se guarda.** Cada observación guarda solo la **tarifa total para todos los pasajeros** (`precio`). El costo total se calcula al evaluar, con los extras vigentes en `viajes.json`. Los extras son un monto fijo por viaje, así que cambiarlos desplaza toda la serie por igual y no altera percentiles ni caídas porcentuales calculadas sobre la tarifa. Cambiar un extra no dispara alertas: las alertas solo se evalúan cuando llega una observación nueva. *(Decisión de Claude.)*
- **Precio diario del viaje.** En modo flexible o mes, el precio del día es el **mínimo entre todas las combinaciones** de salida y estadía dentro de `estadia_dias` que devolvió la fuente ese día. *(Decisión de Claude.)*
- **Series por fuente.** Cada fuente forma su propia serie diaria. Los disparadores (b) caída % y (c) mínimo histórico se evalúan **dentro de la serie de una misma fuente**, para que un cambio de fuente no genere caídas falsas. El disparador (a) umbral se evalúa con cualquier fuente. La clave anti-repetición es viaje + tipo (no incluye la fuente), así que un mismo evento no se avisa dos veces por venir de dos fuentes. SerpApi y fast-flights comparten una serie "en vivo", porque ambos leen Google Flights. *(Decisión de Claude.)*
- **Itinerario elegido.** En el detalle del viaje, el usuario marca una oferta con tramos (solo SerpApi o fast-flights traen horarios) como "elegida". Se guarda en `viajes.json` como `itinerario_elegido` (tramos, horarios, aerolíneas). Contiene datos de vuelo, no personales, y las fechas ya son públicas. La vista Itinerario y el `.ics` usan ese campo. *(Decisión de Claude.)*
- **Self-transfer con datos cacheados.** Las combinaciones se muestran como **"estimado"**, porque Travelpayouts no garantiza horarios. Los tiempos de conexión se validan solo si el tramo trae horarios. Las combinaciones estimadas **nunca disparan alertas**. Antes de comprar, el usuario verifica los horarios en el enlace. *(Decisión de Claude.)*
- **Viajes vencidos.** Cuando la última fecha de salida posible ya pasó, el viaje se marca inactivo automáticamente y su histórico se conserva. *(Decisión de Claude.)*

### 4.5 Secretos (GitHub Actions secrets, nunca en el repo)

`TRAVELPAYOUTS_TOKEN`, `SERPAPI_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SMTP_USER`, `SMTP_PASSWORD` (contraseña de aplicación de Gmail) y `EMAIL_DESTINO`.

## 5. Riesgos y límites por fuente

| Fuente | Límite técnico | Riesgo legal o de términos | Mitigación |
|---|---|---|---|
| **Travelpayouts Data API** | Datos cacheados (2 a 7 días) de búsquedas de otros usuarios. Puede no haber datos en rutas poco buscadas. Límites por minuto (HTTP 429) | Requiere registro como afiliado. Hay que **verificar** si los términos exigen mostrar enlaces de afiliado o atribución | Marcar "precio cacheado" en la UI. Usar los enlaces de compra con marcador de afiliado si lo exige |
| **SerpApi (Google Flights)** | ~250 búsquedas al mes en el plan gratis (algunas fuentes dicen 100: **verificar**). No se acumulan entre meses | Bajo: SerpApi asume la relación con Google | Presupuesto mensual duro en el recolector y aviso al 80% de uso |
| **fast-flights (scraping de Google Flights)** | Frágil: depende del formato interno de Google. Las IPs de datacenter, como las de Actions, pueden quedar bloqueadas o recibir el muro de consentimiento | **Va contra los términos de servicio de Google** (acceso automatizado). Uso personal, de muy bajo volumen y sin cuenta, pero sigue siendo un incumplimiento. El usuario asume el riesgo | Es solo respaldo, con máximo 1 consulta por viaje al día. Se desactiva con un flag y la app sigue funcionando sin él |
| **mindicador.cl / open.er-api.com** | Servicios gratuitos sin SLA | Bajo | Hay dos fuentes con fallback. Si fallan ambas, se usa el último tipo de cambio conocido, marcado como tal |
| **OurAirports** | Datos comunitarios | Dominio público | Snapshot estático, actualizado a mano |
| **Dataset de visas** (por ejemplo passport-index-dataset en GitHub) | Sin reglas de tránsito ni ETIAS/ESTA detallado. Puede estar desactualizado | **Verificar la licencia** antes de incluirlo | Aviso permanente de "verificar en fuente oficial" y notas de tránsito manuales |
| **Feeds RSS de ofertas** | Pueden no existir o cambiar | Términos de cada sitio: **verificar** | Fuera del núcleo. Si no hay feeds viables, se descarta |
| **GitHub Actions** | El cron puede retrasarse u omitirse en horas punta. En repos públicos, los workflows programados se desactivan tras 60 días sin actividad | Las políticas de uso aceptable de Actions limitan usos ajenos al proyecto. La recolección alimenta la propia app publicada, pero es un área gris | Programar el cron en un minuto no redondo. El commit diario mantiene el repo activo. El panel de salud muestra si la última corrida tiene más de 36 h |
| **GitHub Pages** | Sitio público y cacheado (unos minutos de retraso) | Repo público: rutas, fechas y precios quedan visibles (aceptado) | Ningún dato personal en el repo |
| **Token de GitHub en el navegador** | Si se filtra, permite escribir en el repo | — | Token fine-grained de un solo repo con `contents:write` y vencimiento. CSP estricta, sin scripts de terceros |

### 5.1 Punto de control H1: cobertura medida (2026-11-02)

Medición hecha desde GitHub Actions con el token real, sobre la respuesta cruda de `prices_for_dates` (antes de filtrar):

| Destino | Ida y vuelta, marzo 2027 | Solo ida, marzo 2027 | Ida y vuelta, cualquier fecha | Solo ida, cualquier fecha |
|---|---|---|---|---|
| FRA | 0 | 0 | 0 | 0 |
| MAD | 0 | 1 | 8 | 28 |
| NRT | 1 | 1 | 2 | 5 |
| PAR | 2 | 1 | 7 | 5 |
| LON | 0 | 1 | 0 | 7 |
| TYO | 1 | 1 | 2 | 5 |

Resultado: **la caché de Travelpayouts no sirve como fuente base** para rutas largas desde SCL. Hay como máximo 2 fechas con precio por mes, y la mayoría de las combinaciones devuelve 0. El filtro de estadía no explica el problema, porque la respuesta cruda ya viene vacía. Travelpayouts queda como fuente complementaria. Además, mindicador.cl dio timeout desde Actions y se usó el respaldo open.er-api.com, que funcionó.

## 6. Plan por hitos

Cada hito termina con su criterio de aceptación verificable. Se trabaja con superpowers en cada uno (plan, TDD en la lógica Python y de cálculo, review).

**H0. Esqueleto y despliegue**
- Repo público, Pages activo, workflow programado que escribe `data/estado.json` y commitea.
- ✅ La URL de Pages carga una página en español. El workflow corre con `workflow_dispatch` y por cron, y deja un commit con `estado.json` actualizado.

**H1. Recolector base: Travelpayouts + tipos de cambio**
- Módulos de fuente, normalización, almacenamiento mensual y tipos de cambio.
- **Punto de control:** antes de seguir, hay que verificar con el token real que Travelpayouts devuelve datos para SCL→Europa y SCL→Asia/Oceanía. Si la cobertura es pobre (menos de la mitad de las fechas del mes con precio), la fuente base pasa a ser la serie "en vivo" y se recalcula el presupuesto de SerpApi antes de H2.
- ✅ Hay tests unitarios con respuestas grabadas (fixtures) que pasan sin red. Una corrida real con un viaje de ejemplo crea `data/precios/<id>/<mes>.json` con montos en CLP. Si falla la fuente, `estado.json` registra el error y el workflow no falla entero.

**H2. Frontend: Inicio y Detalle con histórico**
- Lista de viajes, gráfico SVG del mínimo diario, bandas de percentil, etiqueta bueno/normal/caro y selector CLP/USD/EUR.
- ✅ Con datos de ejemplo de 30 días, el detalle muestra el gráfico y la etiqueta correcta, verificada contra un cálculo de percentil en un test. Funciona sin errores de consola a 375 px y a 1280 px de ancho.

**H3. Alertas**
- Los tres disparadores, la regla anti-repetición y los canales Telegram, email y `alertas.json`.
- ✅ Hay tests para cada disparador y para la anti-repetición. Una corrida manual con un umbral alto fuerza una alerta que llega a Telegram y al email y aparece en la vista Alertas. Una segunda corrida el mismo día no la reenvía.

**H4. Edición de viajes desde la app**
- Ajustes con token (guardado en `localStorage`) y formulario crear/editar/desactivar viaje vía API de GitHub.
- ✅ Crear un viaje desde el celular genera un commit en `config/viajes.json` y la siguiente corrida lo rastrea. Un conflicto de SHA se informa sin perder lo escrito. La CSP queda verificada en las cabeceras o el meta de la página.

**H5. SerpApi + fast-flights + panel de salud**
- Presupuesto mensual de SerpApi, fallback a fast-flights y percentiles por fuente.
- ✅ Hay un test del reparto de presupuesto: con 5 viajes y 200 consultas al mes no se pasa de 200. Si se simula el agotamiento de cuota, la corrida usa fast-flights. Si se desactiva fast-flights con el flag, la corrida termina bien. El panel de salud muestra el estado de cada fuente y el uso de cuota.

**H6. Calendario de precios y aeropuertos alternativos**
- ✅ Un viaje con modo `mes` muestra una grilla con todas las fechas del mes, coloreada por percentil. Al marcar aeropuertos alternativos aparecen sus precios comparados, y las distancias salen de `aeropuertos.json`.

**H7. Self-transfer y costo total real**
- ✅ Hay un test que con tramos de ejemplo descarta conexiones menores al mínimo y combinaciones cuyo ahorro no supera el margen. El detalle muestra el desglose del costo total (tarifa, equipaje, traslados, recargo self-transfer) en las tres monedas.

**H8. Itinerario, visas y .ics**
- ✅ La vista de itinerario marca conexiones cortas, cambios de aeropuerto y vuelos nocturnos. El checklist indica el pasaporte recomendado por país con su aviso. El `.ics` exportado se importa sin errores en Google Calendar.

**H9. PWA offline**
- ✅ Se puede instalar en Android y en el escritorio. En modo avión muestra los últimos datos con "datos de hace N horas". Lighthouse PWA no reporta fallos de instalabilidad.

**H10. Ofertas y tarifas de error (opcional)**
- ✅ Se hace después de verificar que existen feeds viables. Las ofertas que coinciden con SCL o con los destinos rastreados aparecen en la vista Alertas, marcadas como "oferta externa".

## 7. Decisiones del builder

Estas decisiones las tomó Claude, no el usuario. Se pueden cambiar:
- Los umbrales por defecto: caída del 10%, 14 observaciones mínimas, conexión de 4 h o 6 h, margen self-transfer de CLP 80.000 y presupuesto SerpApi de 200 al mes.
- Gráficos en SVG hecho a mano, sin librería.
- Archivos de precios particionados por viaje y mes.
- Percentiles y alertas de tendencia separados por fuente. SerpApi y fast-flights forman una sola serie "en vivo".
- El precio diario en fechas flexibles es el mínimo entre todas las combinaciones.
- Se guarda la tarifa y el costo total se calcula al evaluar.
- El itinerario elegido se guarda en `viajes.json`.
- Self-transfer con datos cacheados se muestra como "estimado" y sin alertas.
- Pages se sirve desde la raíz del repo.
- La estructura interna de carpetas del código, salvo `config/` y `data/`.

Queda a criterio del builder:
- El diseño visual (se usarán las skills de diseño disponibles).
- La hora exacta del cron.
- El formato de los mensajes de alerta.
- El orden interno de las tareas dentro de cada hito.
