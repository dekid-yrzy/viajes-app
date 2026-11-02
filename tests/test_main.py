import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from recolector.__main__ import ejecutar
from recolector.almacen import escribir_json, leer_json
from recolector.fuentes.travelpayouts import URL
from recolector.red import ErrorRed
from recolector.tipos_cambio import MINDICADOR_URL
from tests.test_travelpayouts import VIAJE
from tests.util import fixture

AHORA = datetime(2026, 11, 2, 11, 5, tzinfo=timezone.utc)
ID = "scl-fra-2027-03"


def falso(travelpayouts=None, tasas=True):
    def get(url, params=None, headers=None, timeout=30):
        if url == URL:
            if travelpayouts is None:
                return fixture("travelpayouts_mes.json")
            if isinstance(travelpayouts, Exception):
                raise travelpayouts
            return travelpayouts
        if tasas and url == MINDICADOR_URL:
            return fixture("mindicador.json")
        raise ErrorRed("caído", estado=503)

    return get


class TestEjecutar(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        inactivo = {**VIAJE, "id": "inactivo-1", "activo": False}
        escribir_json(self.raiz / "config/viajes.json", {"viajes": [VIAJE, inactivo]})

    def tearDown(self):
        self._tmp.cleanup()

    def observaciones(self):
        return leer_json(self.raiz / f"data/precios/{ID}/2026-11.json", None)["observaciones"]

    def test_corrida_completa(self):
        estado = ejecutar(self.raiz, falso(), AHORA, "t")
        self.assertEqual(estado["ultima_corrida"], "2026-11-02T11:05:00Z")
        self.assertEqual(estado["tipos_cambio"], "mindicador")
        self.assertEqual(estado["fuentes"]["travelpayouts"]["estado"], "ok")
        obs = self.observaciones()
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["precio"]["monto"], 1043.2)
        self.assertEqual(obs[0]["precio"]["clp"], 986137)
        self.assertIn("2026-11-02", leer_json(self.raiz / "data/tipos_cambio.json", {}))
        self.assertEqual(leer_json(self.raiz / "data/estado.json", None), estado)

    def test_viaje_inactivo_no_consulta(self):
        ejecutar(self.raiz, falso(), AHORA, "t")
        self.assertNotIn("inactivo-1", leer_json(self.raiz / "data/estado.json", None)["viajes"])
        self.assertFalse((self.raiz / "data/precios/inactivo-1").exists())

    def test_viaje_pasado_se_salta_sin_error(self):
        pasado = {**VIAJE, "id": "pasado", "fechas": {"modo": "mes", "mes": "2026-09"}}
        escribir_json(self.raiz / "config/viajes.json", {"viajes": [pasado]})
        estado = ejecutar(self.raiz, falso(travelpayouts=AssertionError("no debe consultar")), AHORA, "t")
        self.assertEqual(estado["errores"], [])
        self.assertNotIn("pasado", estado["viajes"])

    def test_fuente_falla_no_tumba(self):
        estado = ejecutar(self.raiz, falso(travelpayouts=ErrorRed("HTTP 500", estado=500)), AHORA, "t")
        self.assertEqual(estado["fuentes"]["travelpayouts"]["estado"], "error")
        self.assertEqual(estado["errores"][-1]["viaje_id"], ID)
        self.assertEqual(estado["errores"][-1]["fuente"], "travelpayouts")

    def test_sin_token(self):
        estado = ejecutar(self.raiz, falso(), AHORA, None)
        self.assertEqual(estado["fuentes"]["travelpayouts"], {"estado": "error", "detalle": "falta TRAVELPAYOUTS_TOKEN"})
        self.assertFalse((self.raiz / f"data/precios/{ID}").exists())

    def test_sin_tipos_de_cambio_guarda_clp_null(self):
        estado = ejecutar(self.raiz, falso(tasas=False), AHORA, "t")
        self.assertEqual(estado["tipos_cambio"], "sin_datos")
        self.assertIsNone(self.observaciones()[0]["precio"]["clp"])
        self.assertEqual(leer_json(self.raiz / "data/tipos_cambio.json", {}), {})

    def test_ruta_sin_datos(self):
        estado = ejecutar(self.raiz, falso(travelpayouts={"success": True, "currency": "usd", "data": []}), AHORA, "t")
        self.assertEqual(estado["fuentes"]["travelpayouts"]["estado"], "ok")
        self.assertEqual(estado["viajes"][ID]["fechas_con_precio"], 0)
        self.assertFalse((self.raiz / f"data/precios/{ID}").exists())

    def test_errores_se_recortan_a_20(self):
        escribir_json(self.raiz / "data/estado.json", {"errores": [{"mensaje": str(i)} for i in range(25)]})
        estado = ejecutar(self.raiz, falso(travelpayouts=ErrorRed("HTTP 500", estado=500)), AHORA, "t")
        self.assertEqual(len(estado["errores"]), 20)
        self.assertEqual(estado["errores"][-1]["viaje_id"], ID)


if __name__ == "__main__":
    unittest.main()
