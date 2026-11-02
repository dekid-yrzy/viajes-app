import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from recolector.__main__ import ejecutar
from recolector.almacen import escribir_json, leer_json
from recolector.red import ErrorRed
from tests.test_main import AHORA
from tests.test_main_vivo import AJUSTES, CLAVES, Buscar, get_falso
from tests.test_notificar import ENTORNO, SmtpFalso
from tests.test_travelpayouts import VIAJE


class Post:
    def __init__(self, falla=False):
        self.falla, self.llamadas = falla, 0

    def __call__(self, url, datos, timeout=30):
        self.llamadas += 1
        if self.falla:
            raise ErrorRed("HTTP 401", estado=401)
        return {"ok": True}


class TestEjecutarAlertas(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self.config(2_000_000)

    def tearDown(self):
        self._tmp.cleanup()

    def config(self, umbral):
        escribir_json(self.raiz / "config/viajes.json", {"viajes": [{**VIAJE, "umbral_clp": umbral}]})
        escribir_json(self.raiz / "config/ajustes.json", {**AJUSTES, "url_publica": "https://x.github.io/viajes-app/"})

    def correr(self, post, ahora=AHORA, get=None, entorno=ENTORNO):
        return ejecutar(self.raiz, get or get_falso(), ahora, CLAVES, buscar=Buscar(), pausa=0, entorno=entorno, post_json=post, smtp_factory=SmtpFalso)

    def alertas(self):
        return leer_json(self.raiz / "data/alertas.json", {"alertas": []})["alertas"]

    def test_umbral_alto_dispara_y_notifica_una_vez(self):
        post = Post()
        estado = self.correr(post)
        alertas = self.alertas()
        self.assertEqual([a["tipo"] for a in alertas], ["umbral"])
        self.assertEqual(alertas[0]["canales_enviados"], ["telegram", "email", "app"])
        self.assertEqual(alertas[0]["id"], f"{VIAJE['id']}-umbral-2026-11-02T11:05:00Z")
        self.assertEqual((post.llamadas, estado["alertas_nuevas"]), (1, 1))
        self.assertEqual(estado["fuentes"]["telegram"]["estado"], "ok")
        self.assertIn("SCL → FRA", SmtpFalso.ultimo.enviado.get_content())

    def test_segunda_corrida_mismo_dia_no_reenvia(self):
        post = Post()
        self.correr(post)
        estado = self.correr(post, ahora=AHORA + timedelta(hours=2), get=get_falso("prohibido"))
        self.assertEqual((post.llamadas, estado["alertas_nuevas"], len(self.alertas())), (1, 0, 1))
        self.assertEqual(estado["fuentes"]["telegram"]["estado"], "sin_alertas")

    def test_telegram_falla_alerta_igual_se_guarda(self):
        estado = self.correr(Post(falla=True))
        self.assertEqual(self.alertas()[0]["canales_enviados"], ["email", "app"])
        self.assertEqual(estado["fuentes"]["telegram"], {"estado": "error", "detalle": "HTTP 401"})

    def test_alertas_json_corrupto_se_trata_como_vacio(self):
        (self.raiz / "data").mkdir(exist_ok=True)
        (self.raiz / "data/alertas.json").write_text("{roto", encoding="utf-8")
        self.assertEqual(self.correr(Post())["alertas_nuevas"], 1)

    def test_sin_entorno_guarda_solo_en_app(self):
        ejecutar(self.raiz, get_falso(), AHORA, CLAVES, buscar=Buscar(), pausa=0)
        self.assertEqual(self.alertas()[0]["canales_enviados"], ["app"])

    def test_umbral_bajo_no_dispara(self):
        self.config(1)
        post = Post()
        estado = self.correr(post)
        self.assertEqual((estado["alertas_nuevas"], post.llamadas, self.alertas()), (0, 0, []))

    def test_alerta_que_no_se_pudo_notificar_se_reintenta(self):
        self.correr(Post(), entorno={})  # primera corrida sin secretos: queda solo en la app
        self.assertEqual(self.alertas()[0]["canales_enviados"], ["app"])
        post = Post()
        estado = self.correr(post, ahora=AHORA + timedelta(hours=1))
        self.assertEqual((post.llamadas, estado["alertas_nuevas"]), (1, 1))
        self.assertEqual(self.alertas()[-1]["canales_enviados"], ["telegram", "email", "app"])

    def test_alerta_solo_app_no_se_duplica_sin_canales(self):
        self.correr(Post(), entorno={})
        estado = self.correr(Post(), ahora=AHORA + timedelta(hours=1), entorno={})
        self.assertEqual((estado["alertas_nuevas"], len(self.alertas())), (0, 1))

    def test_alertas_se_recortan_a_200(self):
        escribir_json(self.raiz / "data/alertas.json", {"alertas": [{"viaje_id": "x", "tipo": "umbral", "fecha": "2026-01-01T00:00:00Z", "precio_usd": 1} for _ in range(205)]})
        self.correr(Post())
        self.assertEqual(len(self.alertas()), 200)


if __name__ == "__main__":
    unittest.main()
