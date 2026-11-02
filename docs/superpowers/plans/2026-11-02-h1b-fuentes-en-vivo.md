# H1b: Fuentes en vivo (SerpApi + fast-flights) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el recolector diario siga cada viaje en un par de fechas de referencia con SerpApi (respaldo: fast-flights), guarde el historial de 61 días de Google y barra un calendario semanal con fast-flights.

**Architecture:** Dos módulos de fuente nuevos con la misma convención que `travelpayouts.py`: funciones puras de normalización y una función de consulta con la red inyectada. Un módulo `referencias.py` decide qué fechas sigue cada viaje y lleva la cuota de SerpApi. `__main__.ejecutar` orquesta las tres fuentes por viaje. fast-flights se importa de forma perezosa solo en la función de búsqueda real, así que los tests no lo necesitan instalado.

**Tech Stack:** Python 3.12 stdlib + `fast-flights==2.2` y `primp==0.15.0` (solo en runtime, fijados en `requirements.txt`). Tests con `unittest`.

**Spec:** `docs/SPEC.md`, secciones 4.1, 4.3, 4.4 ("Precio diario del viaje: fechas de referencia"), 5.2 y 5.3.

## Global Constraints

- Se mantienen todas las Global Constraints del plan H0+H1 (`docs/superpowers/plans/2026-11-02-h0-h1-esqueleto-y-recolector.md`).
- Única dependencia externa: `fast-flights==2.2` con `primp==0.15.0`. Las dos versiones van fijadas. Si importar `fast_flights` falla, esa fuente queda en `error` y el resto de la corrida sigue.
- fast-flights siempre con `fetch_mode="common"`, nunca `"fallback"`: ese modo manda la consulta a un servicio de terceros.
- Claves: `SERPAPI_KEY` va como parámetro `api_key` porque SerpApi no acepta cabecera. Nunca se escribe en `estado.json`, en los errores ni en los logs. Los mensajes de error de SerpApi se guardan sin la URL.
- Cuota de SerpApi: como máximo `ajustes.serpapi_presupuesto_mensual` (200) consultas por mes calendario UTC, contadas en `estado.json`.
- SerpApi: `currency=USD`, `hl=es`, `gl=cl`, `adults=pasajeros`. `price` se toma como el **total para todos los pasajeros** y no se multiplica.
- fast-flights: `passengers=Passengers(adults=pasajeros)`. El precio es texto. Solo se acepta el formato `"$1,043"` (USD); cualquier otro formato se descarta.
- Calendario: una vez cada 7 días por viaje (`flexible` y `mes`), con estadía `(estadia_dias[0] + estadia_dias[1]) // 2` y 2 segundos de pausa entre consultas.
- La referencia elegida automáticamente se guarda en `data/referencias.json` y no cambia sola. Si existe, `viaje["referencia"]` gana.

## Review Focus

1. **Cuota de SerpApi agotada a mitad de mes:** no se hace ninguna llamada más a SerpApi, la observación del día sale de fast-flights con `fuente="fast_flights"`, y el estado lo muestra. → test en Task 4.
2. **fast-flights falla en algunas fechas del calendario** (bloqueo o error de parseo): el calendario se guarda con las fechas que sí funcionaron. Si fallan todas, se conserva el calendario anterior sin pisarlo. → test en Task 2.
3. **Precio de fast-flights en otra moneda o formato** (`"CLP 900.000"`, `"€850"`, `""`): se descarta sin interpretarlo mal. → test en Task 2.
4. **Viaje flexible sin referencia y con calendario vacío:** se registra el error del viaje, no se gasta cuota de SerpApi y el resto sigue. → test en Task 4.
5. **Cambio de mes:** el contador de uso de SerpApi vuelve a 0. → test en Task 3.

---

### Task 1: Fuente SerpApi

**Files:**
- Create: `recolector/fuentes/serpapi.py`
- Test: `tests/test_serpapi.py`, `tests/fixtures/serpapi_scl_fra.json`

**Interfaces:**
- Consumes: `red.ErrorRed`, `tipos_cambio.a_clp`.
- Produces:
  - `URL = "https://serpapi.com/search.json"`
  - `parametros(viaje: dict, salida: str, regreso: str | None) -> dict` (sin `api_key`): `engine="google_flights"`, `departure_id`, `arrival_id`, `outbound_date=salida`, `type="1"` y `return_date=regreso` si es ida y vuelta (si no, `type="2"`), `currency="USD"`, `hl="es"`, `gl="cl"` y `adults=viaje["pasajeros"]`.
  - `observacion(resp: dict, viaje: dict, salida: str, regreso: str | None, capturado: str, tasas: dict | None) -> dict | None`. Toma el itinerario de menor `price` entre `best_flights` y `other_flights`. Devuelve `None` si no hay ninguno con `price` entero positivo. Arma el esquema de SPEC 4.3 con:
    - `fuente="serpapi"`, `precio={"monto": float(price), "moneda": "USD", "clp": a_clp(...)}`;
    - `escalas=len(layovers)`, `duracion_min=total_duration`;
    - `aerolineas` = aerolíneas distintas de `flights`, en orden;
    - `tramos=[{"origen", "destino", "salida", "llegada", "aerolinea", "vuelo"}]` desde `flights`;
    - `self_transfer=False`, `enlace=resp["search_metadata"].get("google_flights_url")`;
    - y dos campos extra: `nivel=price_insights.price_level` y `rango_tipico=price_insights.typical_price_range` (o `None`).
  - `historial(resp: dict) -> list[list]`: `[[AAAA-MM-DD (UTC), precio], ...]` desde `price_insights.price_history`, ordenado por fecha. Descarta los puntos malformados.
  - `consultar(viaje, salida, regreso, get_json, clave: str, capturado: str, tasas) -> tuple[dict | None, list[list]]`: llama `get_json(URL, {**parametros(...), "api_key": clave})`. Si `resp` trae `"error"`, lanza `ErrorRed(f"SerpApi: {resp['error']}")`.

- [ ] **Step 1: Fixture.** `serpapi_scl_fra.json`: forma real reducida de la prueba de SPEC 5.3. Lleva `search_metadata` (`status: "Success"`, `google_flights_url`), 2 `best_flights` (971 y 997; el de 971 con 2 tramos SCL→YYZ→FRA de Air Canada, `layovers` [{id YYZ, duration 620}] y `total_duration` 1725), 1 `other_flights` (1013), y `price_insights` con `lowest_price` 971, `price_level` "typical", `typical_price_range` [840, 1100] y `price_history` [[1788393600, 964], [1788480000, 928], [1793577600, 971]]. Incluye además un itinerario con `price` ausente, que debe ignorarse.

- [ ] **Step 2: Tests**

```python
VIAJE = <viaje de ejemplo de SPEC 4.3>
TASAS = {"USD": 945.3, "EUR": 1021.8}

def test_parametros_ida_vuelta(self):
    p = parametros(VIAJE, "2027-03-08", "2027-03-24")
    self.assertEqual((p["engine"], p["departure_id"], p["arrival_id"], p["type"], p["return_date"], p["adults"]),
                     ("google_flights", "SCL", "FRA", "1", "2027-03-24", 1))
    self.assertNotIn("api_key", p)

def test_parametros_solo_ida(self):
    p = parametros({**VIAJE, "tipo": "ida"}, "2027-03-08", None)
    self.assertEqual(p["type"], "2"); self.assertNotIn("return_date", p)

def test_observacion_toma_el_minimo(self):
    o = observacion(fixture("serpapi_scl_fra.json"), VIAJE, "2027-03-08", "2027-03-24", "2026-11-02T11:05:00Z", TASAS)
    self.assertEqual(o["precio"], {"monto": 971.0, "moneda": "USD", "clp": 917886})
    self.assertEqual((o["fuente"], o["escalas"], o["duracion_min"], o["aerolineas"]), ("serpapi", 1, 1725, ["Air Canada"]))
    self.assertEqual([t["destino"] for t in o["tramos"]], ["YYZ", "FRA"])
    self.assertEqual((o["nivel"], o["rango_tipico"]), ("typical", [840, 1100]))

def test_observacion_sin_itinerarios(self):
    self.assertIsNone(observacion({"best_flights": [], "other_flights": []}, VIAJE, "2027-03-08", "2027-03-24", "x", None))

def test_historial_a_fechas(self):
    self.assertEqual(historial(fixture("serpapi_scl_fra.json")), [["2026-09-03", 964], ["2026-09-04", 928], ["2026-11-02", 971]])

def test_consultar_error_lanza_sin_clave_en_mensaje(self):
    with self.assertRaises(ErrorRed) as ctx:
        consultar(VIAJE, "2027-03-08", "2027-03-24", lambda *a, **k: {"error": "Invalid API key."}, "CLAVE", "x", None)
    self.assertNotIn("CLAVE", str(ctx.exception))

def test_consultar_envia_clave(self):
    falso = FalsoGet(fixture("serpapi_scl_fra.json"))  # importar de tests.test_travelpayouts
    obs, hist = consultar(VIAJE, "2027-03-08", "2027-03-24", falso, "CLAVE", "x", None)
    self.assertEqual(falso.llamadas[0][1]["api_key"], "CLAVE")
    self.assertEqual((obs["precio"]["monto"], len(hist)), (971.0, 3))
```

- [ ] **Step 3:** correr `python -m unittest tests.test_serpapi -v` → ERROR por import.
- [ ] **Step 4:** implementar `recolector/fuentes/serpapi.py`.
- [ ] **Step 5:** correr de nuevo → 7 OK. Luego la suite completa `python -m unittest discover -s tests` → OK.
- [ ] **Step 6:** commit `"Fuente SerpApi: observación, price_insights e historial"`.

---

### Task 2: Fuente fast-flights (Google Flights) y calendario

**Files:**
- Create: `recolector/fuentes/google_flights.py`, `requirements.txt`
- Test: `tests/test_google_flights.py`

**Interfaces:**
- Consumes: `tipos_cambio.a_clp`.
- Produces:
  - `requirements.txt` con dos líneas: `fast-flights==2.2` y `primp==0.15.0`.
  - `buscar(viaje: dict, salida: str, regreso: str | None)` es la búsqueda real. Hace `from fast_flights import FlightData, Passengers, get_flights` dentro de la función y llama a `get_flights(..., trip="round-trip" | "one-way", seat="economy", passengers=Passengers(adults=pasajeros), fetch_mode="common")`. Devuelve el `Result` (atributos `flights` y `current_price`; cada vuelo tiene `name`, `price`, `stops`, `duration`, `departure` y `arrival`). No lleva test unitario: es un envoltorio fino y ya se probó en SPEC 5.2.
  - `precio_usd(texto) -> int | None`: `"$1,043"` → 1043, `"$968"` → 968. Cualquier otra cosa → `None`.
  - `observacion(resultado, viaje, salida, regreso, capturado, tasas) -> dict | None`: toma el vuelo de menor `precio_usd`. Devuelve `None` si ninguno es válido. Arma el esquema de SPEC 4.3 con:
    - `fuente="fast_flights"`, `moneda="USD"`;
    - `escalas=stops` (0 si no es entero), `duracion_min=None` y `aerolineas=name.split(", ")`;
    - `tramos=[]`, `enlace=None` y `nivel=resultado.current_price` (o `None`).
  - `estadia_calendario(viaje) -> int | None`: `(estadia_dias[0] + estadia_dias[1]) // 2` si es ida y vuelta; `None` si es solo ida.
  - `calendario(viaje: dict, hoy: date, buscar_fn, generado: str, tasas, pausa: float = 2.0) -> dict | None`: recorre cada fecha de salida de la ventana de `travelpayouts._ventana(viaje)` que sea ≥ `hoy`, con `regreso = salida + estadia_calendario`. Por cada fecha llama a `buscar_fn` y después a `observacion`. Atrapa cualquier excepción por fecha. Entre llamadas hace `time.sleep(pausa)`. Devuelve `{"generado": generado, "estadia_dias": n, "fechas": {salida: {"regreso", "monto", "clp", "nivel"}}, "errores": k}`, o `None` si ninguna fecha dio precio.
  - Para importar `_ventana`, renómbrala a `ventana` en `travelpayouts.py` (función pública) y actualiza sus usos.

- [ ] **Step 1: Tests** (con `types.SimpleNamespace` imitando `Result` y `Flight`; `buscar_fn` falso)

```python
def test_precio_usd(self):
    self.assertEqual([precio_usd(x) for x in ("$1,043", "$968", "CLP 900.000", "€850", "", None)], [1043, 968, None, None, None, None])

def test_observacion_minimo_y_nivel(self):
    r = resultado([vuelo("Air Canada", "$997", 1), vuelo("LATAM, Iberia", "$968", 1), vuelo("X", "€1", 0)], "typical")
    o = observacion(r, VIAJE, "2027-03-08", "2027-03-24", "x", TASAS)
    self.assertEqual((o["precio"]["monto"], o["aerolineas"], o["nivel"], o["fuente"]), (968.0, ["LATAM", "Iberia"], "typical", "fast_flights"))

def test_observacion_sin_precios_validos(self):
    self.assertIsNone(observacion(resultado([vuelo("X", "€1", 0)], "low"), VIAJE, "2027-03-08", "2027-03-24", "x", None))

def test_calendario_mes_usa_estadia_media(self):
    llamadas = []
    def falso(viaje, salida, regreso):
        llamadas.append((salida, regreso)); return resultado([vuelo("A", "$900", 1)], "low")
    cal = calendario(VIAJE, date(2026, 11, 2), falso, "2026-11-02T11:05:00Z", None, pausa=0)
    self.assertEqual(len(llamadas), 31)
    self.assertEqual(llamadas[0], ("2027-03-01", "2027-03-18"))  # estadía (14+21)//2 = 17
    self.assertEqual((cal["estadia_dias"], len(cal["fechas"]), cal["errores"]), (17, 31, 0))

def test_calendario_tolera_fallos_parciales(self):
    def falso(viaje, salida, regreso):
        if salida.endswith(("05", "06")): raise RuntimeError("bloqueado")
        return resultado([vuelo("A", "$900", 1)], "low")
    cal = calendario(VIAJE, date(2026, 11, 2), falso, "x", None, pausa=0)
    self.assertEqual((len(cal["fechas"]), cal["errores"]), (29, 2))

def test_calendario_todo_falla_devuelve_none(self):
    def falso(*a): raise RuntimeError("bloqueado")
    self.assertIsNone(calendario(VIAJE, date(2026, 11, 2), falso, "x", None, pausa=0))
```

- [ ] **Step 2:** correr `python -m unittest tests.test_google_flights -v` → ERROR por import.
- [ ] **Step 3:** implementar el módulo y `requirements.txt`, y renombrar `ventana` en `travelpayouts.py`.
- [ ] **Step 4:** correr de nuevo → 6 OK. La suite completa → OK.
- [ ] **Step 5:** commit `"Fuente fast-flights y calendario semanal"`.

---

### Task 3: Referencias y cuota

**Files:**
- Create: `recolector/referencias.py`
- Test: `tests/test_referencias.py`

**Interfaces:**
- Produces:
  - `fechas_referencia(viaje: dict, guardadas: dict, calendario: dict | None) -> tuple[str, str | None, str] | None`: devuelve `(salida, regreso, origen)`, donde `origen` es `"fija"`, `"usuario"`, `"guardada"` o `"calendario"`. Prioridad:
    1. modo `fija` → sus fechas;
    2. `viaje["referencia"]`;
    3. `guardadas[viaje["id"]]`;
    4. la fecha de menor `monto` en `calendario["fechas"]`, con su `regreso`.
    - Si no hay ninguna, devuelve `None`. En solo ida, `regreso` es `None`.
  - `calendario_vencido(calendario: dict | None, ahora: datetime, dias: int = 7) -> bool`: `True` si es `None` o si `generado` tiene más de `dias` días.
  - `uso_serpapi(previo: dict | None, ahora: datetime) -> dict`: `{"mes": "AAAA-MM", "usadas": n}`. Si el mes cambió o no hay valor previo, `usadas` vuelve a 0.

- [ ] **Step 1: Tests**

```python
def test_fija_usa_sus_fechas(self):
    v = {**VIAJE, "fechas": {"modo": "fija", "salida": "2027-03-10", "regreso": "2027-03-28"}}
    self.assertEqual(fechas_referencia(v, {}, None), ("2027-03-10", "2027-03-28", "fija"))

def test_prioridad_usuario_guardada_calendario(self):
    cal = {"fechas": {"2027-03-05": {"regreso": "2027-03-22", "monto": 900.0}, "2027-03-09": {"regreso": "2027-03-26", "monto": 850.0}}}
    self.assertEqual(fechas_referencia(VIAJE, {}, cal), ("2027-03-09", "2027-03-26", "calendario"))
    guardadas = {VIAJE["id"]: {"salida": "2027-03-05", "regreso": "2027-03-22"}}
    self.assertEqual(fechas_referencia(VIAJE, guardadas, cal), ("2027-03-05", "2027-03-22", "guardada"))
    v = {**VIAJE, "referencia": {"salida": "2027-03-12", "regreso": "2027-03-27"}}
    self.assertEqual(fechas_referencia(v, guardadas, cal), ("2027-03-12", "2027-03-27", "usuario"))

def test_sin_nada_devuelve_none(self):
    self.assertIsNone(fechas_referencia(VIAJE, {}, None))

def test_calendario_vencido(self):
    ahora = datetime(2026, 11, 10, tzinfo=timezone.utc)
    self.assertTrue(calendario_vencido(None, ahora))
    self.assertTrue(calendario_vencido({"generado": "2026-11-02T11:05:00Z"}, ahora))
    self.assertFalse(calendario_vencido({"generado": "2026-11-05T11:05:00Z"}, ahora))

def test_uso_serpapi_reinicia_al_cambiar_mes(self):
    self.assertEqual(uso_serpapi({"mes": "2026-11", "usadas": 120}, datetime(2026, 12, 1, tzinfo=timezone.utc)), {"mes": "2026-12", "usadas": 0})
    self.assertEqual(uso_serpapi({"mes": "2026-11", "usadas": 120}, datetime(2026, 11, 30, tzinfo=timezone.utc)), {"mes": "2026-11", "usadas": 120})
    self.assertEqual(uso_serpapi(None, datetime(2026, 11, 2, tzinfo=timezone.utc)), {"mes": "2026-11", "usadas": 0})
```

- [ ] **Step 2:** correr → ERROR por import. **Step 3:** implementar. **Step 4:** correr → 5 OK y la suite completa OK.
- [ ] **Step 5:** commit `"Fechas de referencia y cuota mensual de SerpApi"`.

---

### Task 4: Orquestador con las tres fuentes

**Files:**
- Modify: `recolector/__main__.py`, `tests/test_main.py`, `tests/test_main_robustez.py`
- Test: `tests/test_main_vivo.py`

**Interfaces:**
- Consumes: Tasks 1–3, `travelpayouts.recolectar`, `almacen.*`.
- Produces: la firma cambia a `ejecutar(raiz: Path, get_json, ahora: datetime, claves: dict, buscar=None, pausa: float = 2.0) -> dict`.
  - `claves = {"travelpayouts": str | None, "serpapi": str | None}`.
  - `buscar` es la búsqueda de fast-flights. **Si es `None`, fast-flights queda desactivado**: no hay calendario ni respaldo. Este es el flag de apagado que pide SPEC 5. `main()` pasa `google_flights.buscar`, salvo que la variable de entorno `DESACTIVAR_FAST_FLIGHTS=1` esté definida.
  - Si no hay clave de SerpApi y `buscar` es `None`, los pasos 2 a 6 se saltan por completo, sin error de referencia.
  - `main()` lee `TRAVELPAYOUTS_TOKEN` y `SERPAPI_KEY` del entorno.
  - Hay que actualizar las llamadas existentes en `test_main.py` y `test_main_robustez.py`: `"t"` pasa a `{"travelpayouts": "t", "serpapi": None}`, y `None` pasa a `{"travelpayouts": None, "serpapi": None}`. Sin `buscar`, esos tests conservan su comportamiento actual.
- Flujo por viaje activo, todo dentro del `try` existente:
  1. Travelpayouts, igual que ahora, si hay clave.
  2. En modo `flexible` o `mes`, si `calendario_vencido(...)`: generar el calendario con `google_flights.calendario`. Si no es `None`, escribir `data/calendario/<id>.json`.
  3. Calcular `ref = fechas_referencia(viaje, guardadas, calendario)`. Si es `None`, registrar el error `"sin fechas de referencia"` (fuente `"referencia"`) y pasar al siguiente viaje. Si `ref` vino de `"calendario"`, guardarla en `data/referencias.json`.
  4. Si hay clave de SerpApi y `uso.usadas < ajustes["serpapi_presupuesto_mensual"]`: `uso.usadas += 1` **antes** de llamar, luego `serpapi.consultar(...)`. Si `historial` no está vacío, escribir `data/historial_google/<id>.json` = `{"salida", "regreso", "actualizado": capturado, "puntos": [...]}`.
  5. Si SerpApi no se usó, falló o devolvió `None`: `google_flights.observacion(buscar(viaje, salida, regreso), ...)`.
  6. Guardar la observación en vivo que haya, con `agregar_observacion`.
- `estado` agrega:
  - `fuentes.serpapi` y `fuentes.fast_flights`, con `{"estado": "ok" | "error" | "cuota_agotada" | "sin_clave", "detalle"}`;
  - `serpapi_uso` (de `uso_serpapi`);
  - por viaje, `referencia: {"salida", "regreso", "origen"}` y `fuente_en_vivo: "serpapi" | "fast_flights" | null`.

- [ ] **Step 1: Tests en `tests/test_main_vivo.py`** (raíz temporal con `config/ajustes.json` de SPEC 4.3 y un viaje `mes`; `get_json` falso que enruta mindicador, Travelpayouts y SerpApi a fixtures; `buscar` falso que cuenta llamadas y devuelve `$900`)

```python
def test_dia_normal_usa_serpapi_y_guarda_historial(self):
    estado = ejecutar(raiz, get_ok, AHORA, CLAVES, buscar=buscar_falso, pausa=0)
    vivo = [o for o in observaciones() if o["fuente"] == "serpapi"]
    self.assertEqual(len(vivo), 1)
    self.assertEqual(estado["serpapi_uso"], {"mes": "2026-11", "usadas": 1})
    self.assertEqual(estado["viajes"][ID]["fuente_en_vivo"], "serpapi")
    self.assertEqual(len(leer_json(raiz / f"data/historial_google/{ID}.json", None)["puntos"]), 3)
    self.assertEqual(buscar_falso.llamadas, 31)  # solo el calendario

def test_referencia_del_calendario_se_guarda_y_no_cambia(self):
    ejecutar(raiz, get_ok, AHORA, CLAVES, buscar=buscar_con_minimo_el_dia_9, pausa=0)
    self.assertEqual(leer_json(raiz / "data/referencias.json", {})[ID]["salida"], "2027-03-09")
    # segunda corrida 8 días después con calendario cuyo mínimo es otro día: la referencia sigue siendo 2027-03-09
    estado = ejecutar(raiz, get_ok, AHORA + timedelta(days=8), CLAVES, buscar=buscar_con_minimo_el_dia_20, pausa=0)
    self.assertEqual(estado["viajes"][ID]["referencia"]["salida"], "2027-03-09")

def test_cuota_agotada_usa_fast_flights_sin_llamar_serpapi(self):
    escribir_json(raiz / "data/estado.json", {"serpapi_uso": {"mes": "2026-11", "usadas": 200}, "errores": []})
    estado = ejecutar(raiz, get_que_falla_si_llaman_a_serpapi, AHORA, CLAVES, buscar=buscar_falso, pausa=0)
    self.assertEqual(estado["fuentes"]["serpapi"]["estado"], "cuota_agotada")
    self.assertEqual(estado["viajes"][ID]["fuente_en_vivo"], "fast_flights")

def test_serpapi_falla_cae_a_fast_flights(self):
    estado = ejecutar(raiz, get_serpapi_500, AHORA, CLAVES, buscar=buscar_falso, pausa=0)
    self.assertEqual(estado["fuentes"]["serpapi"]["estado"], "error")
    self.assertEqual(estado["viajes"][ID]["fuente_en_vivo"], "fast_flights")

def test_sin_referencia_no_gasta_serpapi(self):
    def buscar_bloqueado(*a): raise RuntimeError("bloqueado")
    estado = ejecutar(raiz, get_que_falla_si_llaman_a_serpapi, AHORA, CLAVES, buscar=buscar_bloqueado, pausa=0)
    self.assertEqual(estado["errores"][-1]["fuente"], "referencia")
    self.assertEqual(estado["serpapi_uso"]["usadas"], 0)

def test_calendario_vigente_no_se_regenera(self):
    escribir_json(raiz / f"data/calendario/{ID}.json", {"generado": "2026-11-01T11:00:00Z", "estadia_dias": 17, "fechas": {"2027-03-09": {"regreso": "2027-03-26", "monto": 850.0, "clp": None, "nivel": "low"}}, "errores": 0})
    ejecutar(raiz, get_ok, AHORA, CLAVES, buscar=buscar_falso, pausa=0)
    self.assertEqual(buscar_falso.llamadas, 0)

def test_clave_serpapi_no_aparece_en_estado(self):
    estado = ejecutar(raiz, get_serpapi_500, AHORA, {"travelpayouts": "t", "serpapi": "CLAVE-SECRETA"}, buscar=buscar_falso, pausa=0)
    self.assertNotIn("CLAVE-SECRETA", json.dumps(estado))
```

- [ ] **Step 2:** correr `python -m unittest tests.test_main_vivo -v` → FAIL o ERROR.
- [ ] **Step 3:** implementar los cambios en `__main__.py` y actualizar las llamadas de los tests existentes.
- [ ] **Step 4:** correr la suite completa `python -m unittest discover -s tests -v` → todo OK.
- [ ] **Step 5:** commit `"Orquestador con SerpApi, fast-flights, referencias y calendario"`.

---

### Task 5: Workflow y verificación real

**Files:**
- Modify: `.github/workflows/recolectar.yml`, `README.md`

- [ ] **Step 1:** en el workflow, agregar `pip install -r requirements.txt` antes de los tests. Agregar `SERPAPI_KEY: ${{ secrets.SERPAPI_KEY }}` al `env` del recolector. Cambiar `git add data` por `git add data` más un `git status --short`, para que el log muestre los cambios. En el README, documentar `requirements.txt` y `SERPAPI_KEY`.
- [ ] **Step 2:** commit, push y `gh workflow run recolectar.yml`.
- [ ] **Step 3: Verificación.** La corrida termina en verde y en `main` aparecen:
  - `data/calendario/` con 3 archivos de unas 30 fechas cada uno;
  - `data/referencias.json` con 3 viajes;
  - `data/historial_google/` con 3 archivos de unos 60 puntos;
  - `data/precios/<id>/2026-11.json` con observaciones `serpapi`;
  - en `estado.json`, `serpapi_uso.usadas == 3` y las tres fuentes en `ok`.

  Si fast-flights falla en más de la mitad de las fechas de algún calendario, registrarlo en SPEC 5.2 y avisar al usuario antes de H2.
