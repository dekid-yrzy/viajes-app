import unittest
from datetime import date
from types import SimpleNamespace

from recolector.fuentes.google_flights import calendario, estadia_calendario, observacion, precio_usd
from tests.test_travelpayouts import VIAJE

TASAS = {"USD": 945.3, "EUR": 1021.8}


def vuelo(nombre, precio, escalas):
    return SimpleNamespace(name=nombre, price=precio, stops=escalas, duration="20 hr", departure="x", arrival="y")


def resultado(vuelos, nivel):
    return SimpleNamespace(flights=vuelos, current_price=nivel)


class TestGoogleFlights(unittest.TestCase):
    def test_precio_usd(self):
        self.assertEqual([precio_usd(x) for x in ("$1,043", "$968", "CLP 900.000", "€850", "", None, "$")], [1043, 968, None, None, None, None, None])

    def test_observacion_minimo_y_nivel(self):
        r = resultado([vuelo("Air Canada", "$997", 1), vuelo("LATAM, Iberia", "$968", 1), vuelo("X", "€1", 0)], "typical")
        o = observacion(r, VIAJE, "2027-03-08", "2027-03-24", "x", TASAS)
        self.assertEqual((o["precio"]["monto"], o["aerolineas"], o["nivel"], o["fuente"]), (968.0, ["LATAM", "Iberia"], "typical", "fast_flights"))
        self.assertEqual((o["precio"]["clp"], o["escalas"], o["salida"], o["regreso"]), (915050, 1, "2027-03-08", "2027-03-24"))

    def test_observacion_sin_precios_validos(self):
        self.assertIsNone(observacion(resultado([vuelo("X", "€1", 0)], "low"), VIAJE, "2027-03-08", "2027-03-24", "x", None))

    def test_estadia_calendario(self):
        self.assertEqual((estadia_calendario(VIAJE), estadia_calendario({**VIAJE, "tipo": "ida"})), (17, None))

    def test_calendario_mes_usa_estadia_media(self):
        llamadas = []

        def falso(viaje, salida, regreso):
            llamadas.append((salida, regreso))
            return resultado([vuelo("A", "$900", 1)], "low")

        cal = calendario(VIAJE, date(2026, 11, 2), falso, "2026-11-02T11:05:00Z", None, pausa=0)
        self.assertEqual(len(llamadas), 31)
        self.assertEqual(llamadas[0], ("2027-03-01", "2027-03-18"))
        self.assertEqual((cal["estadia_dias"], len(cal["fechas"]), cal["errores"], cal["generado"]), (17, 31, 0, "2026-11-02T11:05:00Z"))
        self.assertEqual(cal["fechas"]["2027-03-01"], {"regreso": "2027-03-18", "monto": 900.0, "clp": None, "nivel": "low"})

    def test_calendario_tolera_fallos_parciales(self):
        def falso(viaje, salida, regreso):
            if salida.endswith(("05", "06")):
                raise RuntimeError("bloqueado")
            return resultado([vuelo("A", "$900", 1)], "low")

        cal = calendario(VIAJE, date(2026, 11, 2), falso, "x", None, pausa=0)
        self.assertEqual((len(cal["fechas"]), cal["errores"]), (29, 2))

    def test_calendario_todo_falla_devuelve_none(self):
        def falso(*a):
            raise RuntimeError("bloqueado")

        self.assertIsNone(calendario(VIAJE, date(2026, 11, 2), falso, "x", None, pausa=0))


if __name__ == "__main__":
    unittest.main()
