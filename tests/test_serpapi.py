import unittest

from recolector.fuentes.serpapi import consultar, historial, observacion, parametros
from recolector.red import ErrorRed
from tests.test_travelpayouts import VIAJE, FalsoGet
from tests.util import fixture

TASAS = {"USD": 945.3, "EUR": 1021.8}


class TestSerpApi(unittest.TestCase):
    def test_parametros_ida_vuelta(self):
        p = parametros(VIAJE, "2027-03-08", "2027-03-24")
        self.assertEqual(
            (p["engine"], p["departure_id"], p["arrival_id"], p["type"], p["outbound_date"], p["return_date"], p["adults"]),
            ("google_flights", "SCL", "FRA", "1", "2027-03-08", "2027-03-24", 1),
        )
        self.assertEqual((p["currency"], p["hl"], p["gl"]), ("USD", "es", "cl"))
        self.assertNotIn("api_key", p)

    def test_parametros_solo_ida(self):
        p = parametros({**VIAJE, "tipo": "ida"}, "2027-03-08", None)
        self.assertEqual(p["type"], "2")
        self.assertNotIn("return_date", p)

    def test_observacion_toma_el_minimo(self):
        o = observacion(fixture("serpapi_scl_fra.json"), VIAJE, "2027-03-08", "2027-03-24", "2026-11-02T11:05:00Z", TASAS)
        self.assertEqual(o["precio"], {"monto": 971.0, "moneda": "USD", "clp": 917886})
        self.assertEqual((o["fuente"], o["escalas"], o["duracion_min"], o["aerolineas"]), ("serpapi", 1, 1725, ["Air Canada"]))
        self.assertEqual([t["destino"] for t in o["tramos"]], ["YYZ", "FRA"])
        self.assertEqual(o["tramos"][0], {"origen": "SCL", "destino": "YYZ", "salida": "2027-03-08 21:55", "llegada": "2027-03-09 06:15", "aerolinea": "Air Canada", "vuelo": "AC 93"})
        self.assertEqual((o["nivel"], o["rango_tipico"]), ("typical", [840, 1100]))
        self.assertEqual((o["salida"], o["regreso"], o["capturado"]), ("2027-03-08", "2027-03-24", "2026-11-02T11:05:00Z"))
        self.assertTrue(o["enlace"].startswith("https://www.google.com/travel/flights"))

    def test_observacion_sin_itinerarios(self):
        self.assertIsNone(observacion({"best_flights": [], "other_flights": []}, VIAJE, "2027-03-08", "2027-03-24", "x", None))

    def test_historial_a_fechas(self):
        self.assertEqual(historial(fixture("serpapi_scl_fra.json")), [["2026-09-03", 964], ["2026-09-04", 928], ["2026-11-02", 971]])

    def test_consultar_error_lanza_sin_clave_en_mensaje(self):
        with self.assertRaises(ErrorRed) as ctx:
            consultar(VIAJE, "2027-03-08", "2027-03-24", lambda *a, **k: {"error": "Invalid API key."}, "CLAVE", "x", None)
        self.assertNotIn("CLAVE", str(ctx.exception))

    def test_consultar_envia_clave(self):
        falso = FalsoGet(fixture("serpapi_scl_fra.json"))
        obs, hist = consultar(VIAJE, "2027-03-08", "2027-03-24", falso, "CLAVE", "x", None)
        self.assertEqual(falso.llamadas[0][1]["api_key"], "CLAVE")
        self.assertEqual((obs["precio"]["monto"], len(hist)), (971.0, 3))


if __name__ == "__main__":
    unittest.main()
