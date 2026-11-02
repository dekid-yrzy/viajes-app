import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from recolector.__main__ import ejecutar
from recolector.almacen import escribir_json, leer_json
from recolector.fuentes import serpapi, travelpayouts
from recolector.red import ErrorRed
from recolector.tipos_cambio import MINDICADOR_URL
from tests.test_google_flights import resultado, vuelo
from tests.test_main import AHORA, ID
from tests.test_travelpayouts import VIAJE
from tests.util import fixture

CLAVES = {"travelpayouts": "t", "serpapi": "CLAVE"}
AJUSTES = {"serpapi_presupuesto_mensual": 200}


def get_falso(serpapi_respuesta="ok"):
    def get(url, params=None, headers=None, timeout=30):
        if url == MINDICADOR_URL:
            return fixture("mindicador.json")
        if url == travelpayouts.URL:
            return fixture("travelpayouts_mes.json")
        if url == serpapi.URL:
            if serpapi_respuesta == "ok":
                return fixture("serpapi_scl_fra.json")
            if serpapi_respuesta == "prohibido":
                raise AssertionError("no debe llamar a SerpApi")
            raise ErrorRed("HTTP 500", estado=500)
        raise ErrorRed("caído", estado=503)

    return get


class Buscar:
    def __init__(self, dia_minimo=None, falla=False):
        self.dia_minimo, self.falla, self.llamadas = dia_minimo, falla, 0

    def __call__(self, viaje, salida, regreso):
        self.llamadas += 1
        if self.falla:
            raise RuntimeError("bloqueado")
        precio = "$800" if self.dia_minimo and salida == self.dia_minimo else "$900"
        return resultado([vuelo("LATAM", precio, 1)], "typical")


class TestEjecutarEnVivo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        escribir_json(self.raiz / "config/viajes.json", {"viajes": [VIAJE]})
        escribir_json(self.raiz / "config/ajustes.json", AJUSTES)

    def tearDown(self):
        self._tmp.cleanup()

    def observaciones(self, fuente):
        datos = leer_json(self.raiz / f"data/precios/{ID}/2026-11.json", {"observaciones": []})
        return [o for o in datos["observaciones"] if o["fuente"] == fuente]

    def test_dia_normal_usa_serpapi_y_guarda_historial(self):
        buscar = Buscar()
        estado = ejecutar(self.raiz, get_falso(), AHORA, CLAVES, buscar=buscar, pausa=0)
        self.assertEqual(len(self.observaciones("serpapi")), 1)
        self.assertEqual(self.observaciones("fast_flights"), [])
        self.assertEqual(estado["serpapi_uso"], {"mes": "2026-11", "usadas": 1})
        self.assertEqual(estado["viajes"][ID]["fuente_en_vivo"], "serpapi")
        self.assertEqual(estado["fuentes"]["serpapi"]["estado"], "ok")
        self.assertEqual(len(leer_json(self.raiz / f"data/historial_google/{ID}.json", None)["puntos"]), 3)
        self.assertEqual(len(leer_json(self.raiz / f"data/calendario/{ID}.json", None)["fechas"]), 31)
        self.assertEqual(buscar.llamadas, 31)

    def test_referencia_del_calendario_se_guarda_y_no_cambia(self):
        ejecutar(self.raiz, get_falso(), AHORA, CLAVES, buscar=Buscar(dia_minimo="2027-03-09"), pausa=0)
        self.assertEqual(leer_json(self.raiz / "data/referencias.json", {})[ID], {"salida": "2027-03-09", "regreso": "2027-03-26"})
        estado = ejecutar(self.raiz, get_falso(), AHORA + timedelta(days=8), CLAVES, buscar=Buscar(dia_minimo="2027-03-20"), pausa=0)
        self.assertEqual(estado["viajes"][ID]["referencia"], {"salida": "2027-03-09", "regreso": "2027-03-26", "origen": "guardada"})
        self.assertIn("2027-03-20", leer_json(self.raiz / f"data/calendario/{ID}.json", None)["fechas"])

    def test_cuota_agotada_usa_fast_flights_sin_llamar_serpapi(self):
        escribir_json(self.raiz / "data/estado.json", {"serpapi_uso": {"mes": "2026-11", "usadas": 200}, "errores": []})
        estado = ejecutar(self.raiz, get_falso("prohibido"), AHORA, CLAVES, buscar=Buscar(), pausa=0)
        self.assertEqual(estado["fuentes"]["serpapi"]["estado"], "cuota_agotada")
        self.assertEqual(estado["viajes"][ID]["fuente_en_vivo"], "fast_flights")
        self.assertEqual(estado["serpapi_uso"]["usadas"], 200)
        self.assertEqual(len(self.observaciones("fast_flights")), 1)

    def test_serpapi_falla_cae_a_fast_flights(self):
        estado = ejecutar(self.raiz, get_falso("error"), AHORA, CLAVES, buscar=Buscar(), pausa=0)
        self.assertEqual(estado["fuentes"]["serpapi"]["estado"], "error")
        self.assertEqual(estado["viajes"][ID]["fuente_en_vivo"], "fast_flights")

    def test_sin_referencia_no_gasta_serpapi(self):
        estado = ejecutar(self.raiz, get_falso("prohibido"), AHORA, CLAVES, buscar=Buscar(falla=True), pausa=0)
        self.assertEqual(estado["errores"][-1]["fuente"], "referencia")
        self.assertEqual(estado["serpapi_uso"]["usadas"], 0)
        self.assertEqual(estado["fuentes"]["fast_flights"]["estado"], "error")

    def test_calendario_vigente_no_se_regenera(self):
        escribir_json(self.raiz / f"data/calendario/{ID}.json", {"generado": "2026-11-01T11:00:00Z", "completo": True, "estadia_dias": 17, "fechas": {"2027-03-09": {"regreso": "2027-03-26", "monto": 850.0, "clp": None, "nivel": "low"}}, "errores": 0})
        buscar = Buscar()
        estado = ejecutar(self.raiz, get_falso(), AHORA, CLAVES, buscar=buscar, pausa=0)
        self.assertEqual(buscar.llamadas, 0)
        self.assertEqual(estado["viajes"][ID]["referencia"]["salida"], "2027-03-09")

    def test_fast_flights_desactivado_y_sin_serpapi_no_hace_nada_en_vivo(self):
        estado = ejecutar(self.raiz, get_falso("prohibido"), AHORA, {"travelpayouts": "t", "serpapi": None}, pausa=0)
        self.assertEqual(estado["fuentes"]["fast_flights"]["estado"], "desactivado")
        self.assertEqual(estado["fuentes"]["serpapi"]["estado"], "sin_clave")
        self.assertNotIn("referencia", estado["viajes"][ID])

    def test_segunda_corrida_del_mismo_dia_no_gasta_serpapi_ni_scrapea(self):
        ejecutar(self.raiz, get_falso(), AHORA, CLAVES, buscar=Buscar(), pausa=0)
        buscar = Buscar()
        estado = ejecutar(self.raiz, get_falso("prohibido"), AHORA + timedelta(hours=3), CLAVES, buscar=buscar, pausa=0)
        self.assertEqual(estado["serpapi_uso"]["usadas"], 1)
        self.assertEqual(buscar.llamadas, 0)
        self.assertEqual(estado["viajes"][ID]["fuente_en_vivo"], "serpapi")

    def test_calendario_bloqueado_registra_el_motivo_real(self):
        estado = ejecutar(self.raiz, get_falso("prohibido"), AHORA, CLAVES, buscar=Buscar(falla=True), pausa=0)
        self.assertIn("bloqueado", estado["fuentes"]["fast_flights"]["detalle"])

    def test_clave_serpapi_no_aparece_en_estado(self):
        estado = ejecutar(self.raiz, get_falso("error"), AHORA, {"travelpayouts": "t", "serpapi": "CLAVE-SECRETA"}, buscar=Buscar(), pausa=0)
        self.assertNotIn("CLAVE-SECRETA", json.dumps(estado))


if __name__ == "__main__":
    unittest.main()
