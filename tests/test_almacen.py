import tempfile
import unittest
from pathlib import Path

from recolector.almacen import agregar_observacion, escribir_json, leer_json


def obs(capturado, monto):
    return {
        "capturado": capturado,
        "fuente": "travelpayouts",
        "precio": {"monto": monto, "moneda": "USD", "clp": None},
    }


class TestAlmacen(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

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


if __name__ == "__main__":
    unittest.main()
