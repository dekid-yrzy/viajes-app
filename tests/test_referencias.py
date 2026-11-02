import unittest
from datetime import datetime, timezone

from recolector.referencias import calendario_vencido, fechas_referencia, uso_serpapi
from tests.test_travelpayouts import VIAJE


class TestReferencias(unittest.TestCase):
    def test_fija_usa_sus_fechas(self):
        v = {**VIAJE, "fechas": {"modo": "fija", "salida": "2027-03-10", "regreso": "2027-03-28"}}
        self.assertEqual(fechas_referencia(v, {}, None), ("2027-03-10", "2027-03-28", "fija"))

    def test_fija_solo_ida(self):
        v = {**VIAJE, "tipo": "ida", "fechas": {"modo": "fija", "salida": "2027-03-10"}}
        self.assertEqual(fechas_referencia(v, {}, None), ("2027-03-10", None, "fija"))

    def test_prioridad_usuario_guardada_calendario(self):
        cal = {"fechas": {"2027-03-05": {"regreso": "2027-03-22", "monto": 900.0}, "2027-03-09": {"regreso": "2027-03-26", "monto": 850.0}}}
        self.assertEqual(fechas_referencia(VIAJE, {}, cal), ("2027-03-09", "2027-03-26", "calendario"))
        guardadas = {VIAJE["id"]: {"salida": "2027-03-05", "regreso": "2027-03-22"}}
        self.assertEqual(fechas_referencia(VIAJE, guardadas, cal), ("2027-03-05", "2027-03-22", "guardada"))
        v = {**VIAJE, "referencia": {"salida": "2027-03-12", "regreso": "2027-03-27"}}
        self.assertEqual(fechas_referencia(v, guardadas, cal), ("2027-03-12", "2027-03-27", "usuario"))

    def test_sin_nada_devuelve_none(self):
        self.assertIsNone(fechas_referencia(VIAJE, {}, None))
        self.assertIsNone(fechas_referencia(VIAJE, {}, {"fechas": {}}))

    def test_calendario_vencido(self):
        ahora = datetime(2026, 11, 10, tzinfo=timezone.utc)
        self.assertTrue(calendario_vencido(None, ahora))
        self.assertTrue(calendario_vencido({"generado": "2026-11-02T11:05:00Z"}, ahora))
        self.assertFalse(calendario_vencido({"generado": "2026-11-05T11:05:00Z"}, ahora))

    def test_uso_serpapi_reinicia_al_cambiar_mes(self):
        self.assertEqual(uso_serpapi({"mes": "2026-11", "usadas": 120}, datetime(2026, 12, 1, tzinfo=timezone.utc)), {"mes": "2026-12", "usadas": 0})
        self.assertEqual(uso_serpapi({"mes": "2026-11", "usadas": 120}, datetime(2026, 11, 30, tzinfo=timezone.utc)), {"mes": "2026-11", "usadas": 120})
        self.assertEqual(uso_serpapi(None, datetime(2026, 11, 2, tzinfo=timezone.utc)), {"mes": "2026-11", "usadas": 0})


if __name__ == "__main__":
    unittest.main()
