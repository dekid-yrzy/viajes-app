# H0 + H1: Esqueleto y recolector base — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tener un repo público con una página en GitHub Pages y un workflow diario que recolecta precios de Travelpayouts y tipos de cambio, los guarda como JSON versionado y deja constancia en `data/estado.json`.

**Architecture:** Un paquete Python `recolector/` sin dependencias externas. Cada módulo recibe una función `get_json` inyectada, así los tests usan fixtures sin red. `python -m recolector` orquesta: lee `config/viajes.json`, obtiene los tipos de cambio, consulta Travelpayouts por viaje, guarda el mínimo diario en `data/precios/<id>/<AAAA-MM>.json` y escribe el estado. GitHub Actions lo corre una vez al día y commitea `data/`.

**Tech Stack:** Python 3.12 (solo stdlib, tests con `unittest`), HTML/JS vanilla, GitHub Actions, GitHub Pages.

**Spec:** `docs/SPEC.md` (secciones 4.1, 4.3, 4.4, 5 y los hitos H0–H1).

**Alcance:** este plan cubre solo H0 y H1. H1 termina con un punto de control: verificar la cobertura de Travelpayouts para rutas desde SCL. El resultado puede cambiar la fuente base, así que H2+ se planifican después de ese punto.

## Global Constraints

- Cero llamadas a LLM en runtime. Nada depende de Claude ni de suscripciones.
- Python: solo stdlib en este plan. Tests con `python -m unittest discover -s tests -v` desde la raíz del repo.
- Frontend: HTML/CSS/JS vanilla, sin build step, sin scripts de terceros.
- UI y documentación en español. Código, comentarios y commits se escriben en prosa normal.
- JSON: UTF-8, `ensure_ascii=False`, `indent=2`, salto de línea final.
- Fechas de captura en ISO 8601 UTC con `Z` (`2026-11-02T11:05:00Z`). Fechas de vuelo como `AAAA-MM-DD`.
- Montos: `clp` entero; USD/EUR con 2 decimales.
- `precio.monto` = tarifa total para **todos** los pasajeros (Travelpayouts entrega precio por persona: multiplicar por `pasajeros`).
- Ningún secreto ni dato personal en el repo. El token de Travelpayouts va como cabecera `X-Access-Token`, nunca en la URL.
- Una fuente o un viaje que falla nunca hace fallar la corrida completa: se registra en `estado.json` y el proceso termina con código 0.

## Review Focus

1. **Travelpayouts responde `success: true` con `data: []`** (ruta sin datos cacheados): no se escribe ninguna observación, el estado de la fuente es `ok` y la cobertura del viaje queda en `fechas_con_precio: 0`. → test en Task 4 y Task 5.
2. **Ofertas incompletas** (`price` nulo o ausente, `departure_at` ausente): se descartan sin romper el resto. → test en Task 4.
3. **Las dos fuentes de tipo de cambio caídas:** se usa el último día de `data/tipos_cambio.json` y el estado lo marca como `historial`. Si no hay historial, las observaciones se guardan con `clp: null`. → tests en Task 3 y Task 5.
4. **Corrida repetida el mismo día** (dispatch manual dos veces): no duplica observaciones. Por fuente y día queda la de menor `monto`. → test en Task 2.
5. **Viajes inactivos o con todas las fechas en el pasado:** no generan llamadas a la API ni errores. → tests en Task 4 y Task 5.

---

## Requisitos previos (acciones del usuario, antes de Task 1)

Estas acciones no las puede hacer el agente: requieren cuentas, decisiones o cambios en el sistema del usuario.

- [ ] Instalar Python 3.12: `winget install -e --id Python.Python.3.12`, abrir una terminal nueva y confirmar con `python --version` (debe mostrar `Python 3.12.x`).
- [ ] Configurar la identidad de git (hoy está vacía): `git config --global user.name "..."` y `git config --global user.email "..."`.
- [ ] Crear una cuenta en Travelpayouts y copiar el token de API (sección "API token" del perfil). Se usa recién en Task 6.

---

### Task 1: Esqueleto del repo y página placeholder (H0)

**Files:**
- Create: `.gitignore`, `.nojekyll`, `index.html`, `app.js`, `config/ajustes.json`, `config/viajes.json`, `data/estado.json`, `README.md`

**Interfaces:**
- Produces: `config/viajes.json` y `config/ajustes.json` con el esquema exacto de SPEC 4.3. El viaje de ejemplo `scl-fra-2027-03` se copia tal cual del SPEC. `data/estado.json` inicial: `{"ultima_corrida": null, "tipos_cambio": null, "fuentes": {}, "viajes": {}, "errores": []}`.

- [ ] **Step 1: Crear los archivos**

`.gitignore`: `__pycache__/`, `*.pyc`, `.venv/`, `.env`.
`index.html`: `<html lang="es">`, título "Viajes", meta viewport, CSP en meta `default-src 'self'; script-src 'self'; connect-src 'self' https://api.github.com; style-src 'self' 'unsafe-inline'`, un `<main>` con encabezado "Viajes" y un `<p id="estado">Cargando…</p>`, y `<script type="module" src="app.js">`.
`app.js`: `fetch('data/estado.json', {cache: 'no-store'})` y muestra "Última actualización: <fecha en es-CL, zona America/Santiago>" o "Aún no hay datos" si `ultima_corrida` es `null`. Si el fetch falla, muestra "No se pudo cargar el estado". Siempre con `textContent`.
`README.md`: 5–10 líneas en español: qué es, cómo correr los tests y el recolector, y los secretos necesarios (SPEC 4.5).

- [ ] **Step 2: Verificar**

Run: `python -m json.tool config/viajes.json > /dev/null && python -m json.tool config/ajustes.json > /dev/null && python -m json.tool data/estado.json > /dev/null && echo ok`
Expected: `ok`

Run: `python -m http.server 8000` y abrir `http://localhost:8000`.
Expected: se ve "Viajes" y "Aún no hay datos", sin errores en consola.

- [ ] **Step 3: Commit (incluye CLAUDE.md y la documentación ya escrita)**

```bash
git add .
git commit -m "Esqueleto del repo, SPEC y página placeholder"
```

---

### Task 2: Almacenamiento JSON

**Files:**
- Create: `recolector/__init__.py` (vacío), `recolector/almacen.py`
- Test: `tests/__init__.py` (vacío), `tests/test_almacen.py`

**Interfaces:**
- Produces:
  - `leer_json(ruta: Path, defecto: Any) -> Any`: devuelve `defecto` si el archivo no existe.
  - `escribir_json(ruta: Path, datos: Any) -> None`: crea las carpetas padre y escribe de forma atómica (archivo temporal + `os.replace`) con el formato de Global Constraints.
  - `agregar_observacion(raiz: Path, viaje_id: str, obs: dict) -> bool`: archivo `raiz/data/precios/<viaje_id>/<obs["capturado"][:7]>.json` con forma `{"viaje_id": ..., "observaciones": [...]}`. Si ya existe una observación con la misma `fuente` y el mismo día (`capturado[:10]`), la reemplaza solo si el `precio.monto` nuevo es menor. Devuelve `True` si escribió.

- [ ] **Step 1: Escribir los tests**

```python
class TestAlmacen(unittest.TestCase):
    # usar tempfile.TemporaryDirectory() como raiz en setUp
    def test_leer_json_inexistente_devuelve_defecto(self):
        self.assertEqual(leer_json(self.raiz / "no.json", {"a": 1}), {"a": 1})

    def test_escribir_y_leer_conserva_tildes(self):
        escribir_json(self.raiz / "x" / "y.json", {"ciudad": "Múnich"})
        texto = (self.raiz / "x" / "y.json").read_text(encoding="utf-8")
        self.assertIn("Múnich", texto)
        self.assertTrue(texto.endswith("\n"))

    def test_agregar_crea_archivo_mensual(self):
        self.assertTrue(agregar_observacion(self.raiz, "v1", obs("2026-11-02T11:00:00Z", 1000.0)))
        datos = leer_json(self.raiz / "data/precios/v1/2026-11.json", None)
        self.assertEqual(datos["viaje_id"], "v1")
        self.assertEqual(len(datos["observaciones"]), 1)

    def test_mismo_dia_y_fuente_conserva_el_menor(self):
        agregar_observacion(self.raiz, "v1", obs("2026-11-02T11:00:00Z", 1000.0))
        self.assertFalse(agregar_observacion(self.raiz, "v1", obs("2026-11-02T15:00:00Z", 1200.0)))
        self.assertTrue(agregar_observacion(self.raiz, "v1", obs("2026-11-02T18:00:00Z", 900.0)))
        datos = leer_json(self.raiz / "data/precios/v1/2026-11.json", None)
        self.assertEqual([o["precio"]["monto"] for o in datos["observaciones"]], [900.0])

    def test_otro_dia_agrega(self):
        agregar_observacion(self.raiz, "v1", obs("2026-11-02T11:00:00Z", 1000.0))
        agregar_observacion(self.raiz, "v1", obs("2026-11-03T11:00:00Z", 1000.0))
        datos = leer_json(self.raiz / "data/precios/v1/2026-11.json", None)
        self.assertEqual(len(datos["observaciones"]), 2)
```
`obs(capturado, monto)` es un helper del test que arma una observación mínima con `fuente="travelpayouts"` y `precio={"monto": monto, "moneda": "USD", "clp": None}`.

- [ ] **Step 2: Correr y ver que fallan**

Run: `python -m unittest tests.test_almacen -v`
Expected: FAIL / ERROR por `ImportError`.

- [ ] **Step 3: Implementar `recolector/almacen.py`** con las firmas de Interfaces.

- [ ] **Step 4: Correr y ver que pasan**

Run: `python -m unittest tests.test_almacen -v`
Expected: 5 tests OK.

- [ ] **Step 5: Commit** — `git commit -m "Almacenamiento JSON con mínimo diario por fuente"`

---

### Task 3: Tipos de cambio

**Files:**
- Create: `recolector/red.py`, `recolector/tipos_cambio.py`
- Test: `tests/test_tipos_cambio.py`, `tests/fixtures/mindicador.json`, `tests/fixtures/er_api.json`

**Interfaces:**
- Produces (`red.py`):
  - `class ErrorRed(Exception)` con atributo `estado: int | None` (código HTTP o `None` si es timeout, error de conexión o JSON inválido).
  - `get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: float = 30) -> Any`: `urllib.request` con `User-Agent: viajes-app/1.0`. Convierte `HTTPError`, `URLError`, `TimeoutError` y `json.JSONDecodeError` en `ErrorRed`. Este archivo no tiene test unitario (es un envoltorio fino de urllib); se prueba en Task 6 con la corrida real.
- Produces (`tipos_cambio.py`):
  - `MINDICADOR_URL = "https://mindicador.cl/api"`, `ER_API_URL = "https://open.er-api.com/v6/latest/USD"`
  - `desde_mindicador(resp: dict) -> dict`: `{"USD": resp["dolar"]["valor"], "EUR": resp["euro"]["valor"]}`. Si faltan datos o no son números positivos, lanza `ValueError`.
  - `desde_er_api(resp: dict) -> dict`: exige `resp["result"] == "success"`. `USD = rates["CLP"]` y `EUR = rates["CLP"] / rates["EUR"]`, redondeados a 2 decimales. Si no, lanza `ValueError`.
  - `obtener(get_json, historial: dict) -> tuple[dict | None, str]`: prueba mindicador y después er-api (captura `ErrorRed` y `ValueError`). Si ambas fallan, devuelve las tasas de la fecha más reciente de `historial`. El segundo valor es `"mindicador"`, `"er-api"`, `"historial"` o `"sin_datos"` (en ese caso las tasas son `None`).
  - `a_clp(monto: float, moneda: str, tasas: dict | None) -> int | None`: `CLP` → `round(monto)`; `USD`/`EUR` → `round(monto * tasas[moneda])`; con otra moneda o `tasas is None` devuelve `None`.

- [ ] **Step 1: Fixtures**

`mindicador.json`: forma real reducida, `{"version": "1.7.0", "fecha": "2026-11-02T03:00:00.000Z", "dolar": {"codigo": "dolar", "valor": 945.3}, "euro": {"codigo": "euro", "valor": 1021.8}}`.
`er_api.json`: `{"result": "success", "base_code": "USD", "rates": {"USD": 1, "CLP": 950.0, "EUR": 0.92}}`.

- [ ] **Step 2: Escribir los tests**

```python
def test_desde_mindicador(self):
    self.assertEqual(desde_mindicador(fixture("mindicador.json")), {"USD": 945.3, "EUR": 1021.8})

def test_desde_er_api_cruza_eur(self):
    self.assertEqual(desde_er_api(fixture("er_api.json")), {"USD": 950.0, "EUR": 1032.61})

def test_er_api_sin_success_falla(self):
    with self.assertRaises(ValueError):
        desde_er_api({"result": "error"})

def test_obtener_usa_fallback_er_api(self):
    # get_json falso: lanza ErrorRed(503) para MINDICADOR_URL y devuelve el fixture para ER_API_URL
    self.assertEqual(obtener(falso, {}), ({"USD": 950.0, "EUR": 1032.61}, "er-api"))

def test_obtener_ambas_caidas_usa_historial_mas_reciente(self):
    hist = {"2026-10-30": {"USD": 900.0, "EUR": 1000.0}, "2026-11-01": {"USD": 940.0, "EUR": 1020.0}}
    self.assertEqual(obtener(siempre_falla, hist), ({"USD": 940.0, "EUR": 1020.0}, "historial"))

def test_obtener_sin_nada(self):
    self.assertEqual(obtener(siempre_falla, {}), (None, "sin_datos"))

def test_a_clp(self):
    t = {"USD": 945.3, "EUR": 1021.8}
    self.assertEqual(a_clp(1043.2, "USD", t), 986137)
    self.assertEqual(a_clp(500000.4, "CLP", t), 500000)
    self.assertIsNone(a_clp(100, "BRL", t))
    self.assertIsNone(a_clp(100, "USD", None))
```

- [ ] **Step 3: Correr y ver que fallan** — `python -m unittest tests.test_tipos_cambio -v` → ERROR por import.

- [ ] **Step 4: Implementar `red.py` y `tipos_cambio.py`** con las firmas de Interfaces.

- [ ] **Step 5: Correr y ver que pasan** — 7 tests OK.

- [ ] **Step 6: Commit** — `git commit -m "Tipos de cambio CLP con fallback y cliente HTTP stdlib"`

---

### Task 4: Fuente Travelpayouts

**Files:**
- Create: `recolector/fuentes/__init__.py` (vacío), `recolector/fuentes/travelpayouts.py`
- Test: `tests/test_travelpayouts.py`, `tests/fixtures/travelpayouts_mes.json`

**Interfaces:**
- Consumes: `red.ErrorRed`, `tipos_cambio.a_clp`.
- Produces:
  - `URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"`
  - `consultas(viaje: dict, hoy: date) -> list[dict]`: parámetros sin token. Comunes a todas: `origin`, `destination`, `one_way` (`"false"` si `tipo == "ida_vuelta"`, si no `"true"`), `currency="usd"`, `sorting="price"`, `direct="false"`, `limit=1000`. Según el modo:
    - `fija`: `departure_at=salida` y `return_at=regreso` si es ida y vuelta.
    - `flexible`: un `departure_at=AAAA-MM` por cada mes que toque `[salida − margen_dias, salida + margen_dias]`.
    - `mes`: `departure_at=mes`.
    - Se omiten los meses enteramente anteriores a `hoy`. Si no queda ninguno, devuelve `[]`.
  - `ofertas(resp: dict, viaje: dict, hoy: date, capturado: str, tasas: dict | None) -> list[dict]`: normaliza cada elemento de `resp["data"]` al esquema de observación de SPEC 4.3, con `fuente="travelpayouts"`, `monto = round(price * pasajeros, 2)`, `moneda = resp.get("currency", "usd").upper()`, `clp = a_clp(...)`, `escalas = max(transfers, return_transfers or 0)`, `duracion_min = duration`, `aerolineas = [airline]`, `self_transfer=False`, `tramos=[]` y `enlace = "https://www.aviasales.com" + link` (o `None` si no hay link). `salida` y `regreso` son los primeros 10 caracteres de `departure_at` y `return_at`. Descarta:
    - ofertas sin `price` o sin `departure_at`;
    - ofertas con `salida < hoy`;
    - ofertas con salida fuera de la ventana (`fija`: igual a `salida`; `flexible`: `|salida − fechas.salida| ≤ margen_dias`; `mes`: mismo mes);
    - en ida y vuelta, ofertas sin `regreso`, y (salvo en modo `fija`) ofertas cuya estadía `(regreso − salida).days` queda fuera de `estadia_dias[0]..estadia_dias[1]`.
  - `cobertura(lista: list[dict], viaje: dict, hoy: date) -> dict`: `{"ofertas": len(lista), "fechas_con_precio": <salidas distintas>, "fechas_posibles": n}`. `n` es 1 en `fija`; en `flexible`, los días de la ventana que son ≥ `hoy`; en `mes`, los días del mes desde `max(hoy, día 1)`.
  - `recolectar(viaje: dict, get_json, token: str, hoy: date, capturado: str, tasas: dict | None) -> tuple[list[dict], dict]`: llama a `get_json(URL, params, headers={"X-Access-Token": token})` por cada consulta, junta las ofertas, y devuelve `(ofertas, cobertura)`. Si la respuesta trae `success` falso, lanza `ErrorRed(None)` con el mensaje de `resp.get("error")`.

- [ ] **Step 1: Fixture `travelpayouts_mes.json`**

Usar la forma documentada de `prices_for_dates` v3: `{"success": true, "currency": "usd", "data": [...]}`. Cada elemento lleva `origin`, `destination`, `origin_airport`, `destination_airport`, `price`, `airline`, `flight_number`, `departure_at` (`"2027-03-08T23:55:00-03:00"`), `return_at`, `transfers`, `return_transfers`, `duration`, `duration_to`, `duration_back` y `link`. Debe incluir 5 elementos para el viaje del SPEC (`mes=2027-03`, `estadia_dias=[14, 21]`, `pasajeros=1`):
  - A: válido, sale 2027-03-08 y vuelve 2027-03-24, `price` 1043.2;
  - B: válido, sale 2027-03-15 y vuelve 2027-03-31, `price` 1100;
  - C: estadía de 7 días (debe descartarse);
  - D: `price: null` (debe descartarse);
  - E: sale 2027-04-02 (fuera del mes, debe descartarse).

- [ ] **Step 2: Escribir los tests**

```python
HOY = date(2026, 11, 2)
VIAJE = <copia del viaje de ejemplo de SPEC 4.3>

def test_consultas_modo_mes(self):
    self.assertEqual([c["departure_at"] for c in consultas(VIAJE, HOY)], ["2027-03"])
    self.assertEqual(consultas(VIAJE, HOY)[0]["one_way"], "false")

def test_consultas_flexible_cruza_meses(self):
    v = {**VIAJE, "fechas": {"modo": "flexible", "salida": "2027-03-30", "regreso": "2027-04-15", "margen_dias": 3}}
    self.assertEqual([c["departure_at"] for c in consultas(v, HOY)], ["2027-03", "2027-04"])

def test_consultas_fija(self):
    v = {**VIAJE, "fechas": {"modo": "fija", "salida": "2027-03-10", "regreso": "2027-03-28"}}
    c = consultas(v, HOY)[0]
    self.assertEqual((c["departure_at"], c["return_at"]), ("2027-03-10", "2027-03-28"))

def test_consultas_viaje_pasado_vacio(self):
    v = {**VIAJE, "fechas": {"modo": "mes", "mes": "2026-09"}}
    self.assertEqual(consultas(v, HOY), [])

def test_ofertas_filtra_y_normaliza(self):
    lista = ofertas(fixture("travelpayouts_mes.json"), VIAJE, HOY, "2026-11-02T11:05:00Z", {"USD": 945.3, "EUR": 1021.8})
    self.assertEqual([(o["salida"], o["regreso"]) for o in lista], [("2027-03-08", "2027-03-24"), ("2027-03-15", "2027-03-31")])
    self.assertEqual(lista[0]["precio"], {"monto": 1043.2, "moneda": "USD", "clp": 986137})
    self.assertEqual(lista[0]["fuente"], "travelpayouts")
    self.assertTrue(lista[0]["enlace"].startswith("https://www.aviasales.com"))

def test_ofertas_multiplica_pasajeros(self):
    lista = ofertas(fixture("travelpayouts_mes.json"), {**VIAJE, "pasajeros": 2}, HOY, "2026-11-02T11:05:00Z", None)
    self.assertEqual(lista[0]["precio"], {"monto": 2086.4, "moneda": "USD", "clp": None})

def test_ofertas_data_vacia(self):
    self.assertEqual(ofertas({"success": True, "currency": "usd", "data": []}, VIAJE, HOY, "x", None), [])

def test_cobertura_mes(self):
    lista = ofertas(fixture("travelpayouts_mes.json"), VIAJE, HOY, "x", None)
    self.assertEqual(cobertura(lista, VIAJE, HOY), {"ofertas": 2, "fechas_con_precio": 2, "fechas_posibles": 31})

def test_recolectar_envia_token_en_cabecera_y_no_en_url(self):
    # get_json falso que registra (url, params, headers) y devuelve el fixture
    recolectar(VIAJE, falso, "TOKEN123", HOY, "x", None)
    url, params, headers = falso.llamadas[0]
    self.assertEqual(headers, {"X-Access-Token": "TOKEN123"})
    self.assertNotIn("TOKEN123", url + json.dumps(params))

def test_recolectar_success_false_lanza(self):
    with self.assertRaises(ErrorRed):
        recolectar(VIAJE, lambda *a, **k: {"success": False, "error": "bad token"}, "t", HOY, "x", None)
```

- [ ] **Step 3: Correr y ver que fallan** — `python -m unittest tests.test_travelpayouts -v` → ERROR por import.

- [ ] **Step 4: Implementar `recolector/fuentes/travelpayouts.py`** con las firmas de Interfaces. Al principio del archivo va un comentario de una línea: los datos son cacheados (2–7 días) y el precio viene por persona.

- [ ] **Step 5: Correr y ver que pasan** — 10 tests OK.

- [ ] **Step 6: Commit** — `git commit -m "Fuente Travelpayouts: consultas, normalización y cobertura"`

---

### Task 5: Orquestador `python -m recolector`

**Files:**
- Create: `recolector/__main__.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces:
  - `ejecutar(raiz: Path, get_json, ahora: datetime, token: str | None) -> dict`. Devuelve el estado y lo escribe en `raiz/data/estado.json`. Pasos:
    1. Lee `config/viajes.json` y el `data/estado.json` previo (para conservar `errores`).
    2. Obtiene las tasas con `tipos_cambio.obtener(get_json, historial)`, donde `historial` es `data/tipos_cambio.json`. Si la fuente usada es `mindicador` o `er-api`, guarda `historial[hoy] = tasas`.
    3. Recorre los viajes con `activo: true`. Si `consultas(...)` está vacío, el viaje se salta sin error.
    4. Sin token, `fuentes.travelpayouts = {"estado": "error", "detalle": "falta TRAVELPAYOUTS_TOKEN"}` y no se consulta nada.
    5. Con ofertas, se guarda la de menor `monto` con `agregar_observacion`. La cobertura queda en `estado["viajes"][id]`.
    6. Cualquier excepción dentro de un viaje se captura: se agrega a `errores` (`{"fecha", "fuente", "viaje_id", "mensaje"}`), `fuentes.travelpayouts.estado = "error"` y se sigue con el siguiente viaje. `errores` conserva solo los últimos 20.
    7. Escribe `{"ultima_corrida": ahora ISO Z, "tipos_cambio": <fuente usada>, "fuentes": {...}, "viajes": {...}, "errores": [...]}`.
  - `main() -> int`: `ejecutar(Path.cwd(), red.get_json, datetime.now(timezone.utc), os.environ.get("TRAVELPAYOUTS_TOKEN"))`, imprime un resumen de una línea por viaje y devuelve 0.

- [ ] **Step 1: Escribir los tests** (raíz temporal con `config/viajes.json` del SPEC más un viaje inactivo; `get_json` falso que enruta por URL a los fixtures)

```python
AHORA = datetime(2026, 11, 2, 11, 5, tzinfo=timezone.utc)

def test_corrida_completa(self):
    estado = ejecutar(self.raiz, falso_ok, AHORA, "t")
    self.assertEqual(estado["ultima_corrida"], "2026-11-02T11:05:00Z")
    self.assertEqual(estado["fuentes"]["travelpayouts"]["estado"], "ok")
    obs = leer_json(self.raiz / "data/precios/scl-fra-2027-03/2026-11.json", None)["observaciones"]
    self.assertEqual(len(obs), 1)
    self.assertEqual(obs[0]["precio"]["monto"], 1043.2)
    self.assertIn("2026-11-02", leer_json(self.raiz / "data/tipos_cambio.json", {}))

def test_viaje_inactivo_no_consulta(self):
    ejecutar(self.raiz, falso_ok, AHORA, "t")
    self.assertNotIn("inactivo-1", leer_json(self.raiz / "data/estado.json", None)["viajes"])
    self.assertFalse((self.raiz / "data/precios/inactivo-1").exists())

def test_fuente_falla_no_tumba(self):
    estado = ejecutar(self.raiz, falso_travelpayouts_500, AHORA, "t")
    self.assertEqual(estado["fuentes"]["travelpayouts"]["estado"], "error")
    self.assertEqual(estado["errores"][-1]["viaje_id"], "scl-fra-2027-03")

def test_sin_token(self):
    estado = ejecutar(self.raiz, falso_ok, AHORA, None)
    self.assertEqual(estado["fuentes"]["travelpayouts"], {"estado": "error", "detalle": "falta TRAVELPAYOUTS_TOKEN"})

def test_sin_tipos_de_cambio_guarda_clp_null(self):
    ejecutar(self.raiz, falso_sin_tasas, AHORA, "t")
    obs = leer_json(self.raiz / "data/precios/scl-fra-2027-03/2026-11.json", None)["observaciones"]
    self.assertIsNone(obs[0]["precio"]["clp"])

def test_ruta_sin_datos(self):
    estado = ejecutar(self.raiz, falso_data_vacia, AHORA, "t")
    self.assertEqual(estado["fuentes"]["travelpayouts"]["estado"], "ok")
    self.assertEqual(estado["viajes"]["scl-fra-2027-03"]["fechas_con_precio"], 0)

def test_errores_se_recortan_a_20(self):
    escribir_json(self.raiz / "data/estado.json", {"errores": [{"mensaje": str(i)} for i in range(25)]})
    estado = ejecutar(self.raiz, falso_travelpayouts_500, AHORA, "t")
    self.assertEqual(len(estado["errores"]), 20)
```

- [ ] **Step 2: Correr y ver que fallan** — `python -m unittest tests.test_main -v` → ERROR.

- [ ] **Step 3: Implementar `recolector/__main__.py`** con `if __name__ == "__main__": sys.exit(main())`.

- [ ] **Step 4: Correr toda la suite** — `python -m unittest discover -s tests -v` → todos OK (29 tests).

- [ ] **Step 5: Commit** — `git commit -m "Orquestador del recolector con estado y tolerancia a fallos"`

---

### Task 6: Workflow, despliegue y punto de control (cierre de H0 y H1)

**Files:**
- Create: `.github/workflows/recolectar.yml`

**Interfaces:**
- Consumes: `python -m recolector`, secreto `TRAVELPAYOUTS_TOKEN`.

- [ ] **Step 1: Escribir el workflow**

- Disparadores: `schedule: - cron: "17 11 * * *"` (≈08:17 en Chile en horario de verano) y `workflow_dispatch`.
- `permissions: contents: write`.
- `concurrency: {group: recolectar, cancel-in-progress: false}`.
- Pasos:
  - `actions/checkout@v4` y `actions/setup-python@v5` con `python-version: "3.12"`;
  - `python -m unittest discover -s tests`;
  - `python -m recolector` con `env: TRAVELPAYOUTS_TOKEN: ${{ secrets.TRAVELPAYOUTS_TOKEN }}`;
  - commit solo si hay cambios en `data/`: `git config user.name "github-actions[bot]"`, `git config user.email "41898282+github-actions[bot]@users.noreply.github.com"`, `git add data`, `git diff --cached --quiet || (git commit -m "Datos $(date -u +%F)" && git pull --rebase && git push)`.

- [ ] **Step 2: Commit local** — `git commit -m "Workflow diario de recolección"`

- [ ] **Step 3: Publicar (requiere confirmación explícita del usuario: crea un repo público)**

```bash
gh repo create viajes-app --public --source . --push
gh secret set TRAVELPAYOUTS_TOKEN
gh api -X POST repos/{owner}/viajes-app/pages -f "source[branch]=main" -f "source[path]=/"
```
El token lo pega el usuario en el prompt de `gh secret set`. El agente nunca lo ve ni lo escribe.

- [ ] **Step 4: Verificar H0**

Run: `gh workflow run recolectar.yml && gh run watch`
Expected: la corrida termina en verde y aparece un commit `Datos AAAA-MM-DD`. La URL `https://<usuario>.github.io/viajes-app/` muestra "Última actualización: …" con la hora de esa corrida.

- [ ] **Step 5: Punto de control de cobertura (cierre de H1)**

Agregar a `config/viajes.json` dos viajes de prueba más, con modo `mes` en un mes 3–5 meses adelante: SCL→MAD y SCL→NRT (o el destino de Asia/Oceanía que el usuario prefiera). Hacer commit y push, correr el workflow y leer `data/estado.json`.
Criterio: para cada viaje, `fechas_con_precio / fechas_posibles ≥ 0.5`.
Si algún destino queda bajo 0.5, registrar los números en `docs/SPEC.md` (sección 5) y **detenerse**: la fuente base se reevalúa con el usuario antes de planificar H2. Si todos pasan, H1 queda cerrado.
