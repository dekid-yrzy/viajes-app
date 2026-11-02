import unittest

from recolector.__main__ import ejecutar
from recolector.almacen import escribir_json, leer_json
from tests.test_main import AHORA, ID, falso
from tests.test_travelpayouts import VIAJE

import tempfile
from pathlib import Path


class TestEjecutarRobustez(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_viaje_malformado_no_tumba_a_los_demas(self):
        roto = {**VIAJE, "id": "roto", "fechas": {"modo": "flexibe"}}
        sin_id = {k: v for k, v in VIAJE.items() if k != "id"} | {"fechas": {"modo": "fija", "salida": "mal"}}
        escribir_json(self.raiz / "config/viajes.json", {"viajes": [roto, sin_id, VIAJE]})
        estado = ejecutar(self.raiz, falso(), AHORA, "t")
        self.assertEqual([e["viaje_id"] for e in estado["errores"]], ["roto", None])
        self.assertTrue((self.raiz / f"data/precios/{ID}/2026-11.json").exists())
        self.assertEqual(leer_json(self.raiz / "data/estado.json", None), estado)

    def test_estado_y_tipos_cambio_corruptos_no_tumban(self):
        escribir_json(self.raiz / "config/viajes.json", {"viajes": [VIAJE]})
        (self.raiz / "data").mkdir(exist_ok=True)
        (self.raiz / "data/estado.json").write_text("{roto", encoding="utf-8")
        (self.raiz / "data/tipos_cambio.json").write_text("", encoding="utf-8")
        estado = ejecutar(self.raiz, falso(), AHORA, "t")
        self.assertEqual(estado["fuentes"]["travelpayouts"]["estado"], "ok")
        self.assertIn("2026-11-02", leer_json(self.raiz / "data/tipos_cambio.json", {}))

    def test_config_corrupta_queda_registrada_en_estado(self):
        (self.raiz / "config").mkdir()
        (self.raiz / "config/viajes.json").write_text("{roto", encoding="utf-8")
        estado = ejecutar(self.raiz, falso(), AHORA, "t")
        self.assertEqual(estado["errores"][-1]["fuente"], "config")
        self.assertEqual(leer_json(self.raiz / "data/estado.json", None), estado)


if __name__ == "__main__":
    unittest.main()
