import unittest
from datetime import date, timedelta

from recolector.alertas import evaluar, mensaje, serie_en_vivo, suprimir
from tests.test_travelpayouts import VIAJE

HOY = "2026-11-10"
AJUSTES = {"caida_pct_alerta": 10, "min_observaciones_percentil": 14}
TASAS = {"USD": 1000.0, "EUR": 1100.0}
SIN_UMBRAL = {**VIAJE, "umbral_clp": None}


def serie_plana(n, valor, hasta="2026-11-09"):
    fin = date.fromisoformat(hasta)
    return [((fin - timedelta(days=n - 1 - i)).isoformat(), valor) for i in range(n)]


def obs_en_vivo(dia, usd, clp=None, salida="2027-03-01", regreso="2027-03-18", fuente="serpapi"):
    return {
        "capturado": f"{dia}T11:00:00Z",
        "fuente": fuente,
        "salida": salida,
        "regreso": regreso,
        "precio": {"monto": float(usd), "moneda": "USD", "clp": clp},
    }


def obs_tp(dia, usd, clp=None):
    return obs_en_vivo(dia, usd, clp, salida="2027-03-15", regreso="2027-03-31", fuente="travelpayouts")


def tipos(alertas, tipo=None):
    return [a for a in alertas if tipo is None or a["tipo"] == tipo]


class TestAlertas(unittest.TestCase):
    def test_serie_en_vivo_filtra_referencia_y_prefiere_observacion(self):
        hist = {"salida": "2027-03-01", "regreso": "2027-03-18", "puntos": [["2026-11-08", 950], ["2026-11-09", 960]]}
        obs = [obs_en_vivo("2026-11-09", 940), obs_en_vivo("2026-11-10", 930), obs_en_vivo("2026-11-10", 1, salida="2027-03-09"), obs_tp("2026-11-10", 2)]
        self.assertEqual(serie_en_vivo(hist, obs, "2027-03-01", "2027-03-18"), [("2026-11-08", 950), ("2026-11-09", 940.0), ("2026-11-10", 930.0)])
        self.assertEqual(serie_en_vivo({**hist, "salida": "2027-02-01"}, [], "2027-03-01", "2027-03-18"), [])

    def test_umbral_usa_costo_total(self):
        alertas = evaluar(VIAJE, HOY, [obs_en_vivo(HOY, 880, clp=880000)], [], AJUSTES, TASAS)
        self.assertEqual([a["tipo"] for a in alertas], ["umbral"])
        a = alertas[0]
        self.assertEqual((a["costo_total_clp"], a["referencia_clp"], a["referencia_usd"], a["precio_clp"], a["precio_usd"]), (940000, 950000, None, 880000, 880.0))
        self.assertEqual((a["viaje_id"], a["fuente"], a["salida"], a["regreso"]), (VIAJE["id"], "serpapi", "2027-03-01", "2027-03-18"))
        self.assertEqual(evaluar(VIAJE, HOY, [obs_en_vivo(HOY, 900, clp=900000)], [], AJUSTES, TASAS), [])

    def test_umbral_sin_clp_o_sin_umbral_no_evalua(self):
        self.assertEqual(evaluar(VIAJE, HOY, [obs_en_vivo(HOY, 1, clp=None)], [], AJUSTES, None), [])
        self.assertEqual(evaluar(SIN_UMBRAL, HOY, [obs_en_vivo(HOY, 1, clp=1)], [], AJUSTES, TASAS), [])

    def test_umbral_con_travelpayouts(self):
        alertas = evaluar(VIAJE, HOY, [obs_tp(HOY, 800, clp=800000)], [], AJUSTES, TASAS)
        self.assertEqual([a["fuente"] for a in alertas], ["travelpayouts"])

    def test_umbral_toma_la_observacion_mas_barata_de_hoy(self):
        alertas = evaluar(VIAJE, HOY, [obs_tp(HOY, 850, clp=850000), obs_en_vivo(HOY, 800, clp=800000)], [], AJUSTES, TASAS)
        self.assertEqual([(a["fuente"], a["precio_clp"]) for a in alertas], [("serpapi", 800000)])

    def test_caida_pct_contra_mediana_7_dias(self):
        serie = serie_plana(20, 1000) + [(HOY, 890)]
        a = tipos(evaluar(SIN_UMBRAL, HOY, [obs_en_vivo(HOY, 890, clp=890000)], serie, AJUSTES, TASAS), "caida_pct")
        self.assertEqual((len(a), a[0]["referencia_usd"], a[0]["referencia_clp"], a[0]["precio_usd"]), (1, 1000, 1000000, 890))
        serie = serie_plana(20, 1000) + [(HOY, 905)]
        self.assertFalse(tipos(evaluar(SIN_UMBRAL, HOY, [], serie, AJUSTES, TASAS), "caida_pct"))

    def test_caida_requiere_3_puntos_en_7_dias(self):
        serie = [("2026-10-01", 1000), ("2026-11-08", 1000), ("2026-11-09", 1000), (HOY, 800)]
        self.assertFalse(tipos(evaluar(SIN_UMBRAL, HOY, [], serie, AJUSTES, TASAS), "caida_pct"))

    def test_minimo_historico_requiere_14_previos(self):
        serie = serie_plana(14, 1000) + [(HOY, 999)]
        self.assertTrue(tipos(evaluar(SIN_UMBRAL, HOY, [], serie, AJUSTES, TASAS), "minimo_historico"))
        serie = serie_plana(13, 1000) + [(HOY, 999)]
        self.assertFalse(tipos(evaluar(SIN_UMBRAL, HOY, [], serie, AJUSTES, TASAS), "minimo_historico"))
        serie = serie_plana(14, 1000) + [(HOY, 1000)]
        self.assertFalse(tipos(evaluar(SIN_UMBRAL, HOY, [], serie, AJUSTES, TASAS), "minimo_historico"))

    def test_sin_punto_de_hoy_no_evalua_tendencia(self):
        self.assertEqual(evaluar(SIN_UMBRAL, HOY, [], serie_plana(20, 1000), AJUSTES, TASAS), [])

    def test_suprimir_3_dias_salvo_caida_5(self):
        previa = {"viaje_id": VIAJE["id"], "tipo": "umbral", "fecha": "2026-11-08T11:00:00Z", "precio_usd": 900.0}

        def cand(usd, tipo="umbral"):
            return {"viaje_id": VIAJE["id"], "tipo": tipo, "precio_usd": usd}

        self.assertEqual(suprimir([cand(890)], [previa], HOY), [])
        self.assertEqual(len(suprimir([cand(855)], [previa], HOY)), 1)
        self.assertEqual(len(suprimir([cand(890)], [{**previa, "fecha": "2026-11-06T11:00:00Z"}], HOY)), 1)
        self.assertEqual(len(suprimir([cand(890, "caida_pct")], [previa], HOY)), 1)
        self.assertEqual(len(suprimir([cand(890)], [{**previa, "viaje_id": "otro"}], HOY)), 1)

    def test_mensaje(self):
        alerta = evaluar(VIAJE, HOY, [obs_en_vivo(HOY, 880, clp=880000)], [], AJUSTES, TASAS)[0]
        texto = mensaje([alerta], {VIAJE["id"]: VIAJE}, "https://x.github.io/viajes-app/")
        self.assertIn("SCL → FRA", texto)
        self.assertIn("940.000", texto)
        self.assertIn(alerta["motivo"], texto)
        self.assertIn("https://x.github.io/viajes-app/#/viaje/scl-fra-2027-03", texto)


if __name__ == "__main__":
    unittest.main()
