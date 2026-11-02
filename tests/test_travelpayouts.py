import json
import unittest
from datetime import date

from recolector.fuentes.travelpayouts import URL, cobertura, consultas, ofertas, recolectar
from recolector.red import ErrorRed
from tests.util import fixture

HOY = date(2026, 11, 2)
VIAJE = {
    "id": "scl-fra-2027-03",
    "activo": True,
    "origen": "SCL",
    "destino": "FRA",
    "aeropuertos_alternativos": ["MUC", "CDG", "AMS"],
    "tipo": "ida_vuelta",
    "fechas": {"modo": "mes", "mes": "2027-03"},
    "estadia_dias": [14, 21],
    "pasajeros": 1,
    "equipaje": {"facturadas": 1, "costo_estimado_clp": 60000},
    "traslados_clp": 0,
    "umbral_clp": 950000,
    "permite_self_transfer": True,
}
TASAS = {"USD": 945.3, "EUR": 1021.8}


class FalsoGet:
    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = []

    def __call__(self, url, params=None, headers=None, timeout=30):
        self.llamadas.append((url, params, headers))
        return self.respuesta


class TestConsultas(unittest.TestCase):
    def test_consultas_modo_mes(self):
        c = consultas(VIAJE, HOY)
        self.assertEqual([x["departure_at"] for x in c], ["2027-03"])
        self.assertEqual(c[0]["one_way"], "false")
        self.assertEqual((c[0]["origin"], c[0]["destination"], c[0]["currency"]), ("SCL", "FRA", "usd"))

    def test_consultas_flexible_cruza_meses(self):
        v = {**VIAJE, "fechas": {"modo": "flexible", "salida": "2027-03-30", "regreso": "2027-04-15", "margen_dias": 3}}
        self.assertEqual([c["departure_at"] for c in consultas(v, HOY)], ["2027-03", "2027-04"])

    def test_consultas_fija(self):
        v = {**VIAJE, "fechas": {"modo": "fija", "salida": "2027-03-10", "regreso": "2027-03-28"}}
        c = consultas(v, HOY)[0]
        self.assertEqual((c["departure_at"], c["return_at"]), ("2027-03-10", "2027-03-28"))

    def test_consultas_solo_ida(self):
        v = {**VIAJE, "tipo": "ida", "fechas": {"modo": "fija", "salida": "2027-03-10"}}
        c = consultas(v, HOY)[0]
        self.assertEqual(c["one_way"], "true")
        self.assertNotIn("return_at", c)

    def test_consultas_viaje_pasado_vacio(self):
        v = {**VIAJE, "fechas": {"modo": "mes", "mes": "2026-09"}}
        self.assertEqual(consultas(v, HOY), [])


class TestOfertas(unittest.TestCase):
    def test_ofertas_filtra_y_normaliza(self):
        lista = ofertas(fixture("travelpayouts_mes.json"), VIAJE, HOY, "2026-11-02T11:05:00Z", TASAS)
        self.assertEqual([(o["salida"], o["regreso"]) for o in lista], [("2027-03-08", "2027-03-24"), ("2027-03-15", "2027-03-31")])
        self.assertEqual(lista[0]["precio"], {"monto": 1043.2, "moneda": "USD", "clp": 986137})
        self.assertEqual(lista[0]["fuente"], "travelpayouts")
        self.assertEqual(lista[0]["capturado"], "2026-11-02T11:05:00Z")
        self.assertEqual(lista[1]["escalas"], 2)
        self.assertTrue(lista[0]["enlace"].startswith("https://www.aviasales.com/search/"))

    def test_ofertas_multiplica_pasajeros(self):
        lista = ofertas(fixture("travelpayouts_mes.json"), {**VIAJE, "pasajeros": 2}, HOY, "2026-11-02T11:05:00Z", None)
        self.assertEqual(lista[0]["precio"], {"monto": 2086.4, "moneda": "USD", "clp": None})

    def test_ofertas_data_vacia(self):
        self.assertEqual(ofertas({"success": True, "currency": "usd", "data": []}, VIAJE, HOY, "x", None), [])

    def test_ofertas_descarta_salidas_pasadas(self):
        v = {**VIAJE, "fechas": {"modo": "mes", "mes": "2027-03"}}
        self.assertEqual(ofertas(fixture("travelpayouts_mes.json"), v, date(2027, 3, 10), "x", None)[0]["salida"], "2027-03-15")

    def test_cobertura_mes(self):
        lista = ofertas(fixture("travelpayouts_mes.json"), VIAJE, HOY, "x", None)
        self.assertEqual(cobertura(lista, VIAJE, HOY), {"ofertas": 2, "fechas_con_precio": 2, "fechas_posibles": 31})


class TestRecolectar(unittest.TestCase):
    def test_recolectar_envia_token_en_cabecera_y_no_en_url(self):
        falso = FalsoGet(fixture("travelpayouts_mes.json"))
        lista, cob = recolectar(VIAJE, falso, "TOKEN123", HOY, "x", None)
        url, params, headers = falso.llamadas[0]
        self.assertEqual(url, URL)
        self.assertEqual(headers, {"X-Access-Token": "TOKEN123"})
        self.assertNotIn("TOKEN123", url + json.dumps(params))
        self.assertEqual((len(lista), cob["fechas_con_precio"]), (2, 2))

    def test_recolectar_success_false_lanza(self):
        with self.assertRaises(ErrorRed):
            recolectar(VIAJE, FalsoGet({"success": False, "error": "bad token"}), "t", HOY, "x", None)


if __name__ == "__main__":
    unittest.main()


class TestOfertasRobustez(unittest.TestCase):
    def test_items_malformados_se_descartan_sin_perder_los_validos(self):
        resp = fixture("travelpayouts_mes.json")
        valido = resp["data"][0]
        resp["data"] = [
            {**valido, "price": 0},
            {**valido, "price": -5},
            {**valido, "price": "1043"},
            {**valido, "departure_at": "no-es-fecha"},
            {**valido, "return_at": "2027-13-40"},
            valido,
        ]
        lista = ofertas(resp, VIAJE, HOY, "x", None)
        self.assertEqual([o["precio"]["monto"] for o in lista], [1043.2])
