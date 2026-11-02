# H2: Inicio y Detalle con histórico — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que la página de GitHub Pages muestre cada viaje rastreado con su precio actual y una etiqueta bueno/normal/caro, y un detalle con el gráfico del histórico, bandas de percentil y selector CLP/USD/EUR.

**Architecture:** Un frontend estático con ES modules, sin build. La lógica pura (estadística, transformación de datos, formato y geometría del gráfico) va en módulos sin DOM, probados con `node --test`, que viene con Node y no instala nada. Las vistas (`app.js`) hacen `fetch` de los JSON del repo, llaman a esa lógica y pintan con `textContent` y SVG creado con `createElementNS`. La navegación usa el hash: `#/` y `#/viaje/<id>`.

**Tech Stack:** HTML, CSS y JS vanilla (ES2022). Tests con `node --test` (Node 24 local; Node ya viene en `ubuntu-latest`). Un `package.json` mínimo con `"type": "module"` y nada más.

**Spec:** `docs/SPEC.md`: 3 (P1, casos 2 y 5), 4.2, 4.3, 4.4 ("Número de comparación" y "Precio diario del viaje: fechas de referencia") y el hito H2.

## Global Constraints

- Sin dependencias, sin build step y sin scripts de terceros. La CSP de `index.html` no se relaja.
- UI en español (es-CL). Montos con `Intl.NumberFormat("es-CL", {style: "currency", currency})`: CLP sin decimales, USD y EUR con 2.
- Todo dato externo se inserta con `textContent`, `createTextNode` o `setAttribute`. Nunca con `innerHTML`.
- `localStorage` solo para la moneda elegida, siempre envuelto en `try/catch`, y la página funciona igual sin él.
- Umbrales: `min_observaciones_percentil = 14` (de `config/ajustes.json`). Etiqueta `bueno` si precio ≤ p25, `caro` si precio ≥ p75, `normal` en otro caso, y `sin_historia` si hay menos de 14 puntos.
- La etiqueta compara la **tarifa** con el histórico de tarifas. Equivale a comparar el costo total, porque los extras son un monto fijo por viaje (SPEC 4.4).
- Ventana del percentil: los últimos 90 días de la serie Google.
- Colores (skill dataviz, `references/palette.md`, modos claro y oscuro):
  - Serie 1 "Google Flights": `--series-1` `#2a78d6` / `#3987e5`.
  - Serie 2 "Travelpayouts (caché)": `--series-2` `#eb6834` / `#d95926`.
  - Superficie `#fcfcfb` / `#1a1a19`; plano de página `#f9f9f7` / `#0d0d0d`.
  - Tinta `#0b0b0b` / `#f0efec`, secundaria `#52514e` / `#c3c2b7`, atenuada `#898781`.
  - Línea de grilla `#e1e0d9` / `#2c2c2a`; eje `#c3c2b7` / `#383835`.
  - Estado: bueno `#0ca30c`, caro `#ec835a` (serious). Siempre con ícono y texto; el texto nunca va en el color de estado.
  - El modo oscuro se define en `@media (prefers-color-scheme: dark)` bajo `:root:not([data-theme="light"])`, y también en `:root[data-theme="dark"]`.
- Marcas del gráfico: línea de 2 px, puntos de 8 px o más, grilla tenue, un solo eje Y, leyenda visible (2 series), etiqueta directa solo en el último punto, tooltip con crosshair y una tabla accesible equivalente.
- Ancho: sin scroll horizontal a 375 px, con márgenes laterales de 16 px.

## Review Focus

1. **Viaje sin `historial_google` ni observaciones** (recién agregado, o fuentes caídas): la tarjeta y el detalle muestran "Aún sin precios", sin errores en consola ni gráfico vacío roto. → test en Task 2 y verificación en Task 4.
2. **Fecha de captura anterior al primer tipo de cambio conocido** (los 61 días sembrados de Google): se convierte con el tipo de cambio más antiguo disponible, no da `NaN`. → test en Task 2.
3. **Meses de `data/precios` que no existen** (404) al recorrer desde 2026-11: se ignoran sin romper la carga. → verificación en Task 4.
4. **Referencia que cambió** (por ejemplo, la anterior quedó en el pasado): la serie Google incluye solo observaciones de la referencia vigente, sin mezclar precios de otras fechas. → test en Task 2.
5. **`localStorage` bloqueado** (navegación privada estricta): la moneda vuelve a CLP y la página funciona. → verificación en Task 4.

---

### Task 1: Estadística y arnés de tests JS

**Files:**
- Create: `package.json`, `js/estadistica.js`
- Test: `tests/js/estadistica.test.js`

**Interfaces:**
- Produces (`js/estadistica.js`):
  - `percentil(valores: number[], p: number): number | null`: interpolación lineal sobre los valores ordenados, con `pos = (n − 1) · p`. Devuelve `null` si el arreglo está vacío. No muta la entrada.
  - `etiqueta(precio: number, historico: number[], minimo = 14): {clave: "bueno" | "normal" | "caro" | "sin_historia", p25, p50, p75}`.
  - `ETIQUETAS = {bueno: "Buen precio", normal: "Precio normal", caro: "Precio alto", sin_historia: "Sin historia suficiente"}`.
- `package.json`: `{"name": "viajes-app", "private": true, "type": "module", "scripts": {"test": "node --test tests/js/"}}`.

- [ ] **Step 1: Test**

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { percentil, etiqueta } from "../../js/estadistica.js";

test("percentil interpola linealmente", () => {
  const v = [40, 10, 30, 20];
  assert.equal(percentil(v, 0.25), 17.5);
  assert.equal(percentil(v, 0.5), 25);
  assert.equal(percentil(v, 0.75), 32.5);
  assert.deepEqual(v, [40, 10, 30, 20]);
  assert.equal(percentil([], 0.5), null);
  assert.equal(percentil([7], 0.9), 7);
});

test("etiqueta según cuartiles con mínimo de observaciones", () => {
  const hist = Array.from({ length: 20 }, (_, i) => 100 + i * 10); // 100..290
  assert.equal(etiqueta(140, hist).clave, "bueno");   // p25 = 147.5
  assert.equal(etiqueta(200, hist).clave, "normal");
  assert.equal(etiqueta(260, hist).clave, "caro");    // p75 = 242.5
  assert.equal(etiqueta(140, hist.slice(0, 13)).clave, "sin_historia");
  assert.equal(etiqueta(140, hist).p50, 195);
});
```

- [ ] **Step 2:** `node --test tests/js/` → FAIL (no existe el módulo).
- [ ] **Step 3:** implementar `js/estadistica.js` y `package.json`.
- [ ] **Step 4:** `node --test tests/js/` → 2 pass.
- [ ] **Step 5:** commit `"Estadística de percentiles y etiqueta de precio"`.

---

### Task 2: Transformación de datos y formato

**Files:**
- Create: `js/datos.js`, `js/formato.js`
- Test: `tests/js/datos.test.js`

**Interfaces:**
- Produces (`js/datos.js`, funciones puras):
  - `tasaPara(tiposCambio: object, fecha: string): {USD, EUR} | null`: devuelve la tasa de la fecha más reciente que sea ≤ `fecha`. Si no hay ninguna anterior, devuelve la más antigua. Si el objeto está vacío, `null`.
  - `convertir(usd: number, moneda: "CLP" | "USD" | "EUR", tasa): number | null`: `USD` → `usd`; `CLP` → `Math.round(usd * tasa.USD)`; `EUR` → `usd * tasa.USD / tasa.EUR` redondeado a 2 decimales. Sin `tasa`, `null` (salvo para USD).
  - `serieGoogle(historial: object | null, observaciones: object[], referencia: {salida, regreso} | null): {fecha, usd}[]`: une los `historial.puntos` (solo si `historial.salida/regreso` coinciden con `referencia`) con las observaciones `fuente ∈ {serpapi, fast_flights}` de esa misma `salida/regreso`, usando `capturado[:10]` como fecha. Si dos datos caen en la misma fecha, gana la observación. Resultado ordenado por fecha.
  - `serieTravelpayouts(observaciones): {fecha, usd}[]`: `fuente == "travelpayouts"`, ordenada.
  - `ventana(serie, dias = 90): serie`: los puntos de los últimos `dias` días contados desde la última fecha de la serie.
  - `costoTotalClp(viaje, tarifaClp: number | null): number | null`: `tarifaClp + (equipaje.costo_estimado_clp ?? 0) + (traslados_clp ?? 0)`.
  - `mesesDesde(inicio: "AAAA-MM", hasta: "AAAA-MM"): string[]`, ambos extremos incluidos.
- Produces (`js/formato.js`):
  - `moneda(valor: number | null, codigo): string`: `"—"` si es `null`. Usa `Intl.NumberFormat("es-CL", …)`.
  - `fechaCorta(iso: string): string`: `"8 mar 2027"` (`es-CL`, zona `UTC` para fechas `AAAA-MM-DD`).
  - `fechaHora(iso: string): string`: en `America/Santiago`.

- [ ] **Step 1: Tests** (con datos en línea)

```js
const TASAS = { "2026-11-02": { USD: 990.8, EUR: 1150.0 }, "2026-11-03": { USD: 1000, EUR: 1160 } };
test("tasaPara usa la más reciente anterior y, si no hay, la más antigua", () => {
  assert.deepEqual(tasaPara(TASAS, "2026-11-05"), { USD: 1000, EUR: 1160 });
  assert.deepEqual(tasaPara(TASAS, "2026-11-02"), { USD: 990.8, EUR: 1150.0 });
  assert.deepEqual(tasaPara(TASAS, "2026-09-03"), { USD: 990.8, EUR: 1150.0 });
  assert.equal(tasaPara({}, "2026-11-02"), null);
});
test("convertir", () => {
  const t = { USD: 1000, EUR: 1160 };
  assert.equal(convertir(966, "CLP", t), 966000);
  assert.equal(convertir(966, "EUR", t), 832.76);
  assert.equal(convertir(966, "USD", null), 966);
  assert.equal(convertir(966, "CLP", null), null);
});
test("serieGoogle une historial y observaciones de la referencia vigente", () => {
  const ref = { salida: "2027-03-01", regreso: "2027-03-18" };
  const hist = { ...ref, puntos: [["2026-11-01", 950], ["2026-11-02", 960]] };
  const obs = [
    { fuente: "serpapi", capturado: "2026-11-02T11:00:00Z", salida: "2027-03-01", regreso: "2027-03-18", precio: { monto: 966 } },
    { fuente: "fast_flights", capturado: "2026-11-03T11:00:00Z", salida: "2027-03-01", regreso: "2027-03-18", precio: { monto: 970 } },
    { fuente: "serpapi", capturado: "2026-11-04T11:00:00Z", salida: "2027-03-09", regreso: "2027-03-26", precio: { monto: 1 } },
    { fuente: "travelpayouts", capturado: "2026-11-04T11:00:00Z", salida: "2027-03-01", regreso: "2027-03-18", precio: { monto: 2 } },
  ];
  assert.deepEqual(serieGoogle(hist, obs, ref), [
    { fecha: "2026-11-01", usd: 950 }, { fecha: "2026-11-02", usd: 966 }, { fecha: "2026-11-03", usd: 970 },
  ]);
  assert.deepEqual(serieGoogle({ salida: "2027-02-01", regreso: "2027-02-10", puntos: [["2026-11-01", 1]] }, [], ref), []);
  assert.deepEqual(serieGoogle(null, [], null), []);
});
test("ventana, costo total y meses", () => {
  const serie = [{ fecha: "2026-07-01", usd: 1 }, { fecha: "2026-10-01", usd: 2 }, { fecha: "2026-11-02", usd: 3 }];
  assert.deepEqual(ventana(serie, 90).map((p) => p.usd), [2, 3]);
  assert.equal(costoTotalClp({ equipaje: { costo_estimado_clp: 60000 }, traslados_clp: 0 }, 957151), 1017151);
  assert.equal(costoTotalClp({}, null), null);
  assert.deepEqual(mesesDesde("2026-11", "2027-02"), ["2026-11", "2026-12", "2027-01", "2027-02"]);
});
test("formato", () => {
  assert.equal(moneda(null, "CLP"), "—");
  assert.match(moneda(957151, "CLP"), /957\.151/);
  assert.equal(fechaCorta("2027-03-08"), "8 mar 2027");
});
```

- [ ] **Step 2:** `node --test tests/js/` → FAIL. **Step 3:** implementar. **Step 4:** → todo pass. Si `fechaCorta` incluye un punto por la abreviatura de `es-CL` (`"8 mar. 2027"`), ajustar la implementación para quitarlo, no el test.
- [ ] **Step 5:** commit `"Transformación de series, conversión de moneda y formato"`.

---

### Task 3: Geometría del gráfico

**Files:**
- Create: `js/grafico.js`
- Test: `tests/js/grafico.test.js`

**Interfaces:**
- Produces:
  - `escalaLineal([d0, d1], [r0, r1]): (v) => number`. Si `d0 == d1`, devuelve el centro del rango.
  - `ticksY(min, max, cantidad = 4): number[]`: valores "redondos" (pasos 1, 2 o 5 × 10ⁿ) que cubren `[min, max]`.
  - `geometria(series: {id, puntos: {fecha, valor}[]}[], banda: {p25, p75, p50} | null, ancho, alto, margen = {arriba: 16, derecha: 56, abajo: 28, izquierda: 72}): {x, y, ticks, rutas: {id, d}[], puntos: {id, cx, cy, fecha, valor}[], banda: {y25, y75, y50} | null}`:
    - El eje X es temporal: va de la fecha mínima a la máxima de todas las series.
    - El eje Y va de `min(valores, p25) · 0.95` a `max(valores, p75) · 1.05`, y luego se ajusta a los ticks.
    - Cada ruta es `"M x,y L x,y …"` con coordenadas redondeadas a 1 decimal. Una serie de un solo punto no tiene ruta, solo punto.
  - `dibujar(svg: SVGElement, geo, opciones: {formatoY, formatoX, etiquetaUltimo}): void`: DOM puro con `createElementNS`, sin lógica de datos. Pinta la grilla y las etiquetas Y, la banda p25–p75 (relleno `--series-1` al 12 %) con la línea p50 punteada, las rutas, los puntos (radio 4) y la etiqueta directa del último punto de la serie 1. No lleva test unitario; se verifica en el navegador (Task 4).

- [ ] **Step 1: Tests**

```js
test("escalaLineal", () => {
  const e = escalaLineal([0, 10], [100, 200]);
  assert.equal(e(5), 150);
  assert.equal(escalaLineal([3, 3], [0, 10])(3), 5);
});
test("ticksY redondos", () => {
  assert.deepEqual(ticksY(840, 1350), [800, 1000, 1200, 1400]);
});
test("geometria arma rutas y puntos dentro del área", () => {
  const geo = geometria(
    [{ id: "google", puntos: [{ fecha: "2026-11-01", valor: 900 }, { fecha: "2026-11-03", valor: 1000 }] },
     { id: "tp", puntos: [{ fecha: "2026-11-02", valor: 950 }] }],
    { p25: 900, p50: 950, p75: 1000 }, 400, 200);
  assert.equal(geo.rutas.length, 1);
  assert.match(geo.rutas[0].d, /^M 72,\d+(\.\d)? L 344,\d+(\.\d)?$/);
  assert.equal(geo.puntos.length, 3);
  for (const p of geo.puntos) { assert.ok(p.cx >= 72 && p.cx <= 344); assert.ok(p.cy >= 16 && p.cy <= 172); }
  assert.ok(geo.banda.y75 < geo.banda.y25);
});
```

- [ ] **Step 2:** → FAIL. **Step 3:** implementar. **Step 4:** → pass.
- [ ] **Step 5:** commit `"Geometría y dibujo SVG del gráfico de precios"`.

---

### Task 4: Vistas Inicio y Detalle

**Files:**
- Create: `estilos.css`
- Modify: `index.html`, `app.js`

**Interfaces:**
- Consumes: Tasks 1–3.
- Carga, en `app.js`:
  - `config/viajes.json`, `config/ajustes.json`, `data/estado.json` y `data/tipos_cambio.json`;
  - por viaje, `data/historial_google/<id>.json` y `data/precios/<id>/<mes>.json` para cada mes de `mesesDesde("2026-11", <mes actual UTC>)`. Un 404 vale como "sin datos" (Review Focus 3);
  - todo con `cache: "no-store"`. El comentario `// shortcut: recorre meses desde 2026-11; con más de 24 meses conviene un índice generado por el recolector`.
- **Referencia vigente:** `estado.viajes[id].referencia`. Si no está, `viaje.referencia` o las fechas de un viaje `fija`.
- **Cabecera:** título "Viajes", "Actualizado: <fechaHora(estado.ultima_corrida)>" y un selector de moneda (`<select>` con CLP, USD y EUR) que se guarda en `localStorage["moneda"]` con `try/catch` (Review Focus 5).
- **Inicio (`#/`)**, una tarjeta-enlace por viaje activo:
  - "SCL → FRA";
  - fechas de referencia, estadía en días y pasajeros;
  - precio actual (último punto de la serie Google, convertido a la moneda elegida);
  - chip de etiqueta con ícono (✓ bueno, ▲ caro, • normal, ○ sin historia) y texto de `ETIQUETAS`;
  - "Google: típico/bajo/alto", tomado del `nivel` de la última observación en vivo;
  - "Costo total estimado: …" en CLP.
  - Sin precios: "Aún sin precios" (Review Focus 1).
- **Detalle (`#/viaje/<id>`):**
  - volver a Inicio, ruta y fechas de referencia;
  - precio actual grande, con chip y costo total con su desglose (tarifa, equipaje, traslados);
  - "Rango típico según Google: X – Y", tomado de `rango_tipico` de la última observación SerpApi y convertido;
  - el gráfico (series Google y Travelpayouts en la moneda elegida, banda p25–p75 de `ventana(serieGoogle, 90)`);
  - leyenda con clave de línea por serie;
  - tooltip con crosshair: una línea vertical que se ajusta a la fecha más cercana y muestra todas las series en esa fecha. Se activa con el puntero y con las flechas del teclado sobre el gráfico (`tabindex="0"`);
  - `<details><summary>Ver tabla</summary>` con una tabla de fecha, Google y Travelpayouts;
  - enlace "Ver en Google Flights" si la última observación SerpApi trae `enlace`.
- **CSS:** los tokens de Global Constraints como custom properties en `:root`. `body` con fondo explícito, `font-family: system-ui, sans-serif` y números con `font-variant-numeric: tabular-nums`. Tarjetas en grilla `repeat(auto-fill, minmax(280px, 1fr))` y foco visible.

- [ ] **Step 1:** implementar `estilos.css`, `index.html` (agregar `<link rel="stylesheet" href="estilos.css">`, sin cambiar la CSP) y `app.js`.
- [ ] **Step 2: Verificación en el navegador** con `preview_start` (configuración `viajes-app` de `.claude/launch.json`) sobre los datos reales del repo (hacer `git pull` antes):
  - en `#/` aparecen 3 tarjetas con precio en CLP; las etiquetas vienen de los 61 puntos de historia;
  - el detalle de `scl-fra-2027-03` muestra la línea Google con unos 61 puntos, la banda, la leyenda y la etiqueta del último punto;
  - el tooltip responde al mouse y a las flechas;
  - cambiar a USD muestra 966 en FRA y la elección persiste al recargar;
  - `read_console_messages` no muestra errores;
  - a 375 px de ancho (`resize_window` mobile) no hay scroll horizontal (`document.documentElement.scrollWidth <= 375`) y lo mismo a 1280 px;
  - en modo oscuro (`resize_window colorScheme: "dark"`) el texto es legible.
  - Para Review Focus 1, editar temporalmente `config/viajes.json` en local con un viaje nuevo sin datos y revisar Inicio y Detalle. Revertir después sin commitear.
- [ ] **Step 3:** commit `"Vistas Inicio y Detalle con histórico, percentiles y moneda"`.

---

### Task 5: CI y publicación

**Files:**
- Modify: `.github/workflows/recolectar.yml`, `README.md`

- [ ] **Step 1:** en el workflow, agregar el paso `node --test tests/js/` después de los tests de Python. En el README, documentar `node --test tests/js/` y la estructura `js/`.
- [ ] **Step 2:** `node --test tests/js/` y `python -m unittest discover -s tests` en local → todo pass. Commit `"Tests JS en CI"`.
- [ ] **Step 3:** después de la revisión final y la fusión en `main`: push, y verificar en https://dekid-yrzy.github.io/viajes-app/ (en el navegador integrado) que Inicio y un Detalle cargan con datos reales y sin errores de consola. Lanzar `gh workflow run recolectar.yml` y confirmar que el paso de tests JS pasa en Actions.
