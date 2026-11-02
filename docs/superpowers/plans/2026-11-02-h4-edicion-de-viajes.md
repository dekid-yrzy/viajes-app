# H4: Edición de viajes desde la app — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Poder crear, editar, desactivar y reactivar viajes desde la página (también desde el celular). Cada cambio queda como un commit en `config/viajes.json` hecho con un token personal de GitHub que vive solo en el navegador.

**Architecture:** Dos módulos puros nuevos, probados con `node --test`:
- `js/github.js`: lectura y escritura de un archivo con la API REST de contenidos, más base64 UTF-8. Recibe `fetch` inyectado.
- `js/viajes.js`: conversión formulario ↔ viaje, validación y aplicación del cambio a la lista.

`app.js` agrega tres vistas: `#/ajustes` (token y lista de todos los viajes), `#/viaje/nuevo` y `#/viaje/<id>/editar`. Al guardar se relee el archivo para tener el SHA vigente, se aplica el cambio sobre esa versión y se escribe con ese SHA.

**Tech Stack:** JS vanilla (ES2022), `fetch`, `TextEncoder`/`TextDecoder` y `btoa`/`atob`. Sin dependencias.

**Spec:** `docs/SPEC.md`, secciones 4.2 ("Edición", "Seguridad" y "Datos personales solo en `localStorage`"), 4.3 (`config/viajes.json`), 4.4 ("Precio diario del viaje: fechas de referencia") y el hito H4.

## Global Constraints

- **Token:**
  - Es un token *fine-grained* de GitHub, con acceso solo al repo `viajes-app` y permiso **Contents: Read and write**.
  - Se guarda en `localStorage["github_token"]` (con `try/catch`) y solo se envía a `https://api.github.com`, en la cabecera `Authorization: Bearer <token>`.
  - Nunca va en una URL, en el DOM visible (el campo es `type="password"` y se vacía después de guardarlo), en `console` ni en mensajes de error.
- **Repo:** por defecto se deduce de la URL de Pages (`<owner>.github.io/<repo>/`). En `localhost` o en otro host se usa `config/ajustes.json → "repo"` (agregar `"repo": "dekid-yrzy/viajes-app"`). Rama `main`. Ruta `config/viajes.json`.
- **API:**
  - Lectura: `GET https://api.github.com/repos/{owner}/{repo}/contents/config/viajes.json?ref=main`, que trae `content` en base64 (con saltos de línea) y `sha`.
  - Escritura: `PUT` al mismo endpoint con `{message, content, sha, branch: "main"}`.
  - Cabeceras: `Accept: application/vnd.github+json` y `X-GitHub-Api-Version: 2022-11-28`.
- **Errores, siempre en español:**
  - `409` o `422` con SHA desactualizado → `conflicto`: "El archivo cambió en GitHub mientras editabas. Vuelve a guardar." El formulario conserva todo lo escrito.
  - `401` → `token`: "Token inválido o vencido. Revísalo en Ajustes."
  - `403` o `404` → `permiso`: "El token no tiene acceso de escritura a este repo."
  - Error de red → `red`.
- **Formato del archivo escrito:** `JSON.stringify({viajes}, null, 2) + "\n"`, en UTF-8.
- **Mensaje del commit:** `"Viajes: crea <id>"`, `"Viajes: edita <id>"`, `"Viajes: desactiva <id>"` o `"Viajes: reactiva <id>"`.
- **Validación** (borde de confianza: lo que el usuario escribe termina en el repo y lo lee el recolector):
  - `origen` y `destino`: 3 letras A–Z (se pasan a mayúsculas) y distintos entre sí.
  - `tipo`: `ida_vuelta` o `ida`.
  - Fechas:
    - `fija`: `salida` obligatoria y `regreso` si es ida y vuelta.
    - `flexible`: `salida`, `regreso` si es ida y vuelta, y `margen_dias` entero entre 1 y 14.
    - `mes`: `AAAA-MM`.
    - En viajes **nuevos**, la salida (o el mes) no puede estar en el pasado.
    - `regreso` > `salida`.
  - `estadia_dias`: obligatoria si es ida y vuelta y el modo no es `fija`. Enteros entre 1 y 90, con mínimo ≤ máximo.
  - `pasajeros`: entero entre 1 y 9.
  - `equipaje.facturadas`: entero entre 0 y 5. Costos y traslados: enteros ≥ 0 (CLP).
  - `umbral_clp`: vacío (`null`) o entero > 0.
  - `aeropuertos_alternativos`: lista de códigos IATA separados por coma.
  - `referencia` (opcional, solo en `flexible` o `mes`): `salida` y, si es ida y vuelta, `regreso`, dentro de la ventana del viaje.
  - `id`: en viajes nuevos se sugiere como `<origen>-<destino>-<AAAA-MM>` en minúsculas, con sufijo `-2`, `-3`… si ya existe. Formato `^[a-z0-9-]{3,60}$`. No se puede cambiar al editar.
- Los campos que el formulario no conoce y que ya estaban en el viaje se conservan al editar (se hace `{...original, ...cambios}`).
- Textos de UI en español. Todo dato se inserta con `textContent`/`value`, nunca con `innerHTML`. La CSP no cambia: `connect-src` ya incluye `https://api.github.com`.

## Review Focus

1. **Conflicto de SHA** (otro cambio en `config/viajes.json` entre la lectura y la escritura): se muestra el mensaje de conflicto y **no se pierde nada de lo escrito** en el formulario. → test en Task 1 y verificación en Task 4.
2. **Token vencido o revocado** (401): mensaje claro y ningún dato perdido. El token no aparece en ningún mensaje. → test en Task 1.
3. **Entrada inválida** (IATA en minúsculas o de 4 letras, regreso antes de la salida, estadía mínima mayor que la máxima, id repetido): errores junto a cada campo y **no se hace ningún `PUT`**. → test en Task 2 y verificación en Task 4.
4. **Texto con tildes o "→" en el archivo:** el base64 UTF-8 ida y vuelta conserva los caracteres exactos. → test en Task 1.
5. **Sin token configurado:** la lectura de la app sigue igual. Los botones de edición llevan a Ajustes con una explicación. → verificación en Task 4.

---

### Task 1: Cliente de la API de contenidos de GitHub

**Files:**
- Create: `js/github.js`
- Test: `tests/js/github.test.js`

**Interfaces:**
- Produces:
  - `aBase64(texto: string): string` y `desdeBase64(b64: string): string`, en UTF-8. `desdeBase64` ignora los saltos de línea.
  - `repoDesdeUbicacion(hostname: string, pathname: string, repoAjustes?: string): {owner, repo} | null`: `dekid-yrzy.github.io` con `/viajes-app/...` → `{owner: "dekid-yrzy", repo: "viajes-app"}`. En otro host usa `repoAjustes` (`"owner/repo"`). Sin datos, `null`.
  - `class ErrorGithub extends Error`, con `tipo: "conflicto" | "token" | "permiso" | "red" | "otro"` y `mensaje` ya en español. El `message` nunca incluye el token.
  - `leerArchivo({owner, repo, token}, ruta, fetchFn = fetch): Promise<{datos: object, sha: string}>`.
  - `escribirArchivo({owner, repo, token}, ruta, datos, sha, mensaje, fetchFn = fetch): Promise<string>`: devuelve el `content.sha` nuevo.
  - `probarToken({owner, repo, token}, fetchFn = fetch): Promise<{escritura: boolean}>`: `GET /repos/{owner}/{repo}`, con `escritura = permissions.push === true`.

- [ ] **Step 1: Tests** (con `fetch` falso que registra las llamadas y devuelve `{ok, status, json()}`)

```js
test("base64 UTF-8 ida y vuelta, con saltos de línea", () => {
  const texto = '{"ruta": "SCL → FRA", "nota": "Múnich, ñandú"}\n';
  const b64 = aBase64(texto);
  assert.equal(desdeBase64(b64.replace(/(.{20})/g, "$1\n")), texto);
});
test("repo desde la URL de Pages o de ajustes", () => {
  assert.deepEqual(repoDesdeUbicacion("dekid-yrzy.github.io", "/viajes-app/"), { owner: "dekid-yrzy", repo: "viajes-app" });
  assert.deepEqual(repoDesdeUbicacion("localhost", "/", "dekid-yrzy/viajes-app"), { owner: "dekid-yrzy", repo: "viajes-app" });
  assert.equal(repoDesdeUbicacion("localhost", "/"), null);
});
test("leerArchivo decodifica y devuelve el sha; el token va solo en la cabecera", async () => {
  const f = falso([{ status: 200, body: { content: aBase64('{"viajes":[]}\n'), sha: "abc" } }]);
  const r = await leerArchivo(CFG, "config/viajes.json", f);
  assert.deepEqual(r, { datos: { viajes: [] }, sha: "abc" });
  assert.equal(f.llamadas[0].url, "https://api.github.com/repos/dekid-yrzy/viajes-app/contents/config/viajes.json?ref=main");
  assert.equal(f.llamadas[0].opciones.headers.Authorization, "Bearer TOKEN-SECRETO");
  assert.ok(!f.llamadas[0].url.includes("TOKEN"));
});
test("escribirArchivo hace PUT con sha, rama y contenido formateado", async () => {
  const f = falso([{ status: 200, body: { content: { sha: "nuevo" } } }]);
  const sha = await escribirArchivo(CFG, "config/viajes.json", { viajes: [] }, "abc", "Viajes: crea x", f);
  const cuerpo = JSON.parse(f.llamadas[0].opciones.body);
  assert.equal(sha, "nuevo");
  assert.equal(f.llamadas[0].opciones.method, "PUT");
  assert.deepEqual([cuerpo.sha, cuerpo.branch, cuerpo.message], ["abc", "main", "Viajes: crea x"]);
  assert.equal(desdeBase64(cuerpo.content), '{\n  "viajes": []\n}\n');
});
test("errores tipados en español sin el token", async () => {
  for (const [status, tipo] of [[409, "conflicto"], [422, "conflicto"], [401, "token"], [403, "permiso"], [404, "permiso"], [500, "otro"]]) {
    const e = await escribirArchivo(CFG, "config/viajes.json", {}, "abc", "m", falso([{ status, body: { message: "x" } }])).catch((x) => x);
    assert.ok(e instanceof ErrorGithub);
    assert.equal(e.tipo, tipo);
    assert.ok(!e.message.includes("TOKEN-SECRETO"));
  }
  const red = await leerArchivo(CFG, "config/viajes.json", async () => { throw new TypeError("Failed to fetch"); }).catch((x) => x);
  assert.equal(red.tipo, "red");
});
test("probarToken informa permiso de escritura", async () => {
  assert.deepEqual(await probarToken(CFG, falso([{ status: 200, body: { permissions: { push: true } } }])), { escritura: true });
  assert.deepEqual(await probarToken(CFG, falso([{ status: 200, body: { permissions: { push: false } } }])), { escritura: false });
});
```

`CFG = {owner: "dekid-yrzy", repo: "viajes-app", token: "TOKEN-SECRETO"}`. `falso(respuestas)` devuelve una función `async (url, opciones)` que registra `{url, opciones}` y responde en orden.

- [ ] **Step 2:** `node --test "tests/js/*.test.js"` → falla. **Step 3:** implementar. **Step 4:** → todo pass.
- [ ] **Step 5:** commit `"Cliente de la API de contenidos de GitHub"`.

---

### Task 2: Modelo y validación de viajes

**Files:**
- Create: `js/viajes.js`
- Test: `tests/js/viajes.test.js`

**Interfaces:**
- Produces:
  - `aFormulario(viaje: object | null, ajustes: object): object`: valores planos para el formulario. Las fechas van como `AAAA-MM-DD`, los números como string, y las listas unidas con `", "`. Sin viaje, usa los valores por defecto: `origen = ajustes.origen_defecto ?? "SCL"`, `tipo = "ida_vuelta"`, `modo = "mes"`, `estadia_min = 14`, `estadia_max = 21`, `pasajeros = 1`, `facturadas = 1`, `costo_equipaje = 60000`, `traslados = 0`, `activo = true` y `permite_self_transfer = true`.
  - `validar(valores: object, {existentes: object[], original: object | null, hoy: string}): {viaje: object | null, errores: object}`: si `errores` (`{campo: "mensaje"}`) no está vacío, `viaje` es `null`. Arma el viaje con el esquema exacto de SPEC 4.3 (`fechas` según el modo, `referencia` solo si se ingresó) y hace `{...original, ...viaje}` al editar.
  - `idSugerido(origen, destino, fechas, existentes): string`.
  - `aplicar(lista: object[], viaje: object, idOriginal: string | null): object[]`: reemplaza el viaje con `id === idOriginal` o lo agrega al final. No muta la entrada.
  - `cambiarActivo(lista, id, activo): object[]`.

- [ ] **Step 1: Tests** (`HOY = "2026-11-02"`; `BASE = aFormulario(null, {origen_defecto: "SCL"})` con `destino: "fra"` y `mes: "2027-03"`)

```js
test("crea un viaje mes válido con id sugerido y esquema de SPEC 4.3", () => {
  const { viaje, errores } = validar({ ...BASE, destino: "fra", mes: "2027-03", umbral: "950000" }, { existentes: [], original: null, hoy: HOY });
  assert.deepEqual(errores, {});
  assert.equal(viaje.id, "scl-fra-2027-03");
  assert.deepEqual(viaje.fechas, { modo: "mes", mes: "2027-03" });
  assert.deepEqual(viaje.estadia_dias, [14, 21]);
  assert.deepEqual(viaje.equipaje, { facturadas: 1, costo_estimado_clp: 60000 });
  assert.equal(viaje.umbral_clp, 950000);
  assert.equal(viaje.destino, "FRA");
});
test("id repetido recibe sufijo", () => {
  const { viaje } = validar({ ...BASE, destino: "FRA", mes: "2027-03" }, { existentes: [{ id: "scl-fra-2027-03" }], original: null, hoy: HOY });
  assert.equal(viaje.id, "scl-fra-2027-03-2");
});
test("errores por campo y sin viaje", () => {
  const casos = [
    [{ destino: "FRAN" }, "destino"],
    [{ destino: "SCL" }, "destino"],
    [{ modo: "fija", salida: "2027-03-10", regreso: "2027-03-01" }, "regreso"],
    [{ estadia_min: "21", estadia_max: "14" }, "estadia_min"],
    [{ pasajeros: "0" }, "pasajeros"],
    [{ mes: "2026-09" }, "mes"],
    [{ umbral: "-5" }, "umbral"],
    [{ alternativos: "MUC, cdgx" }, "alternativos"],
    [{ modo: "flexible", salida: "2027-03-10", regreso: "2027-03-28", margen: "30" }, "margen"],
    [{ ref_salida: "2027-04-02", ref_regreso: "2027-04-20" }, "ref_salida"],
  ];
  for (const [cambio, campo] of casos) {
    const r = validar({ ...BASE, destino: "FRA", mes: "2027-03", ...cambio }, { existentes: [], original: null, hoy: HOY });
    assert.equal(r.viaje, null, campo);
    assert.ok(r.errores[campo], `${campo}: ${JSON.stringify(r.errores)}`);
  }
});
test("editar conserva campos desconocidos, el id y permite fechas ya pasadas", () => {
  const original = { id: "scl-fra-2026-09", activo: true, origen: "SCL", destino: "FRA", tipo: "ida_vuelta", fechas: { modo: "mes", mes: "2026-09" }, estadia_dias: [14, 21], pasajeros: 1, equipaje: { facturadas: 1, costo_estimado_clp: 60000 }, traslados_clp: 0, umbral_clp: null, permite_self_transfer: true, aeropuertos_alternativos: [], campo_futuro: 7 };
  const { viaje, errores } = validar({ ...aFormulario(original, {}), pasajeros: "2" }, { existentes: [original], original, hoy: HOY });
  assert.deepEqual(errores, {});
  assert.deepEqual([viaje.id, viaje.pasajeros, viaje.campo_futuro], ["scl-fra-2026-09", 2, 7]);
});
test("referencia opcional dentro de la ventana", () => {
  const { viaje } = validar({ ...BASE, destino: "FRA", mes: "2027-03", ref_salida: "2027-03-09", ref_regreso: "2027-03-26" }, { existentes: [], original: null, hoy: HOY });
  assert.deepEqual(viaje.referencia, { salida: "2027-03-09", regreso: "2027-03-26" });
});
test("solo ida no exige regreso ni estadía", () => {
  const { viaje, errores } = validar({ ...BASE, destino: "MAD", tipo: "ida", modo: "fija", salida: "2027-03-10", regreso: "" }, { existentes: [], original: null, hoy: HOY });
  assert.deepEqual(errores, {});
  assert.deepEqual(viaje.fechas, { modo: "fija", salida: "2027-03-10" });
  assert.equal(viaje.estadia_dias, undefined);
});
test("aplicar y cambiarActivo no mutan", () => {
  const lista = [{ id: "a", activo: true }];
  assert.deepEqual(aplicar(lista, { id: "b" }, null).map((v) => v.id), ["a", "b"]);
  assert.deepEqual(aplicar(lista, { id: "a", x: 1 }, "a"), [{ id: "a", x: 1 }]);
  assert.equal(cambiarActivo(lista, "a", false)[0].activo, false);
  assert.equal(lista[0].activo, true);
});
```

- [ ] **Step 2:** → falla. **Step 3:** implementar. **Step 4:** → pass.
- [ ] **Step 5:** commit `"Modelo y validación de viajes"`.

---

### Task 3: Vistas de Ajustes y formulario

**Files:**
- Modify: `app.js`, `index.html`, `estilos.css`, `config/ajustes.json` (agregar `"repo"`)

**Interfaces:**
- Consumes: Tasks 1–2.
- **Cabecera:** enlace "Ajustes" junto a "Alertas".
- **`#/ajustes`:**
  - Formulario del token: campo `type="password"` con `autocomplete="off"`, más los botones "Guardar token", "Probar" y "Borrar token".
  - Estado del token: "Token guardado en este navegador" o "Sin token". "Probar" muestra "Puede escribir en dekid-yrzy/viajes-app" o el error en español. El token guardado nunca se muestra.
  - Una nota de 3 pasos para crear el token, con un enlace a `https://github.com/settings/personal-access-tokens/new`: acceso solo al repo `viajes-app`, Contents: Read and write, y vencimiento.
  - La lista de **todos** los viajes (activos e inactivos), cada uno con "Editar" y "Desactivar"/"Reactivar", más un botón "Agregar viaje".
- **`#/viaje/nuevo` y `#/viaje/<id>/editar`:**
  - Un formulario con `<label>` por campo, agrupado en "Ruta", "Fechas", "Pasajeros y equipaje" y "Alertas". Los grupos de fechas se muestran u ocultan según el modo y el tipo (con el atributo `hidden`).
  - Errores en un `<p class="error-campo">` debajo de cada campo, más `aria-invalid="true"` y `aria-describedby`. Al primer error se le da foco.
  - "Guardar":
    1. `validar`;
    2. si es válido, `leerArchivo` (SHA fresco), `aplicar` sobre los datos leídos y `escribirArchivo`;
    3. si funciona, actualiza la lista en memoria, navega al detalle (o a Ajustes si el viaje quedó inactivo) y muestra un aviso: "Guardado. El recolector lo tomará en la próxima corrida diaria."
    4. si falla (`ErrorGithub`), muestra `e.mensaje` arriba del formulario y **no** limpia el formulario.
  - Sin token, el formulario muestra "Configura tu token en Ajustes para guardar" con un enlace, y el botón Guardar queda deshabilitado.
- **Detalle:** enlace "Editar viaje".
- **Inicio:** enlace "Agregar viaje" al final de las tarjetas.
- El botón Guardar se deshabilita mientras hay una petición en curso, para evitar doble envío.

- [ ] **Step 1:** implementar.
- [ ] **Step 2: Verificación en el navegador** (preview local, **sin token real**; el agente no ingresa tokens):
  - **Sin token:** Ajustes muestra "Sin token", el formulario muestra el aviso y Guardar está deshabilitado (Review Focus 5).
  - **Errores de validación:** con un `localStorage["github_token"] = "falso"` puesto desde la consola, llenar el formulario con un destino `"fran"` y un regreso anterior a la salida. Aparecen los errores junto a cada campo y no se hace ningún `fetch` a `api.github.com` (`read_network_requests`, Review Focus 3).
  - **Conflicto simulado:** interceptar `window.fetch` desde la consola para que el `PUT` responda 409. Aparece el mensaje de conflicto y los campos conservan sus valores (Review Focus 1).
  - **Token inválido:** con el token falso contra la API real, la respuesta es 401 y aparece "Token inválido o vencido…".
  - **Ancho y consola:** a 375 px el formulario no tiene scroll horizontal y no hay errores de consola.
  - Al terminar, borrar el `localStorage` de prueba.
- [ ] **Step 3:** commit `"Vistas de Ajustes y edición de viajes"`.

---

### Task 4: Prueba real con el usuario

- [ ] **Step 1:** después de la revisión final, fusionar en `main` y verificar el despliegue de Pages.
- [ ] **Step 2 (usuario):** crear el token fine-grained, guardarlo en Ajustes desde el celular o el computador y crear un viaje de prueba (por ejemplo SCL→LIS, mes 2027-04).
- [ ] **Step 3: Verificación:** `git log -1 -- config/viajes.json` muestra `"Viajes: crea scl-lis-2027-04"`. Lanzar `gh workflow run recolectar.yml`; el estado incluye `scl-lis-2027-04` con referencia del calendario y un precio. Después, el usuario lo desactiva desde la app y el siguiente commit dice `"Viajes: desactiva …"`.
