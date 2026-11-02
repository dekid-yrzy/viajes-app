import unittest

from recolector.red import ErrorRed
from recolector.tipos_cambio import ER_API_URL, MINDICADOR_URL, a_clp, desde_er_api, desde_mindicador, obtener
from tests.util import fixture, siempre_falla


class TestTiposCambio(unittest.TestCase):
    def test_desde_mindicador(self):
        self.assertEqual(desde_mindicador(fixture("mindicador.json")), {"USD": 945.3, "EUR": 1021.8})

    def test_desde_mindicador_valor_invalido_falla(self):
        with self.assertRaises(ValueError):
            desde_mindicador({"dolar": {"valor": 0}, "euro": {"valor": None}})

    def test_desde_er_api_cruza_eur(self):
        self.assertEqual(desde_er_api(fixture("er_api.json")), {"USD": 950.0, "EUR": 1032.61})

    def test_er_api_sin_success_falla(self):
        with self.assertRaises(ValueError):
            desde_er_api({"result": "error"})

    def test_obtener_usa_fallback_er_api(self):
        def falso(url, params=None, headers=None, timeout=30):
            if url == MINDICADOR_URL:
                raise ErrorRed("caído", estado=503)
            self.assertEqual(url, ER_API_URL)
            return fixture("er_api.json")

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


if __name__ == "__main__":
    unittest.main()


class TestTiposCambioRobustez(unittest.TestCase):
    def test_respuesta_que_no_es_dict_pasa_a_la_siguiente_fuente(self):
        def falso(url, params=None, headers=None, timeout=30):
            return [] if url == MINDICADOR_URL else ["no", "dict"]

        self.assertEqual(obtener(falso, {}), (None, "sin_datos"))

    def test_mindicador_rechaza_booleanos(self):
        with self.assertRaises(ValueError):
            desde_mindicador({"dolar": {"valor": True}, "euro": {"valor": 1000.0}})
