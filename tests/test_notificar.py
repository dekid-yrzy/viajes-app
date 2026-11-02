import json
import smtplib
import unittest

from recolector.notificar import enviar
from recolector.red import ErrorRed

ENTORNO = {"TELEGRAM_BOT_TOKEN": "123:SECRETO", "TELEGRAM_CHAT_ID": "42", "SMTP_USER": "yo@gmail.com", "SMTP_PASSWORD": "app", "EMAIL_DESTINO": "yo@gmail.com"}


class SmtpFalso:
    ultimo = None

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.login_args, self.enviado = None, None
        type(self).ultimo = self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, *args):
        self.login_args = args

    def send_message(self, msg):
        self.enviado = msg


class TestNotificar(unittest.TestCase):
    def test_telegram_ok(self):
        llamadas = []

        def post(url, datos, timeout=30):
            llamadas.append((url, datos))
            return {"ok": True}

        estado = enviar("hola", "asunto", ENTORNO, post, smtp_factory=SmtpFalso)
        self.assertEqual(estado["telegram"]["estado"], "ok")
        self.assertEqual(llamadas[0], ("https://api.telegram.org/bot123:SECRETO/sendMessage", {"chat_id": "42", "text": "hola", "disable_web_page_preview": True}))

    def test_telegram_ok_false_es_error(self):
        estado = enviar("hola", "asunto", ENTORNO, lambda *a, **k: {"ok": False}, smtp_factory=SmtpFalso)
        self.assertEqual(estado["telegram"], {"estado": "error", "detalle": "RuntimeError"})

    def test_telegram_401_no_filtra_token_y_email_sigue(self):
        def falla(url, datos, timeout=30):
            raise ErrorRed(f"fallo en {url}", estado=401)

        estado = enviar("hola", "asunto", ENTORNO, falla, smtp_factory=SmtpFalso)
        self.assertEqual(estado["telegram"], {"estado": "error", "detalle": "HTTP 401"})
        self.assertEqual(estado["email"]["estado"], "ok")
        self.assertNotIn("SECRETO", json.dumps(estado))

    def test_email_arma_mensaje(self):
        enviar("cuerpo", "Viajes: 1 alerta(s) de precio", ENTORNO, lambda *a, **k: {"ok": True}, smtp_factory=SmtpFalso)
        s = SmtpFalso.ultimo
        self.assertEqual((s.enviado["Subject"], s.enviado["To"], s.enviado["From"], s.login_args), ("Viajes: 1 alerta(s) de precio", "yo@gmail.com", "yo@gmail.com", ("yo@gmail.com", "app")))
        self.assertEqual((s.host, s.port, s.timeout), ("smtp.gmail.com", 465, 30))
        self.assertEqual(s.enviado.get_content().strip(), "cuerpo")

    def test_canales_sin_configurar(self):
        estado = enviar("x", "y", {}, lambda *a, **k: self.fail("no debe llamar"), smtp_factory=SmtpFalso)
        self.assertEqual((estado["telegram"]["estado"], estado["email"]["estado"]), ("sin_configurar", "sin_configurar"))

    def test_email_falla_se_reporta(self):
        class SmtpRoto(SmtpFalso):
            def login(self, *a):
                raise smtplib.SMTPAuthenticationError(535, b"bad credentials app")

        estado = enviar("x", "y", ENTORNO, lambda *a, **k: {"ok": True}, smtp_factory=SmtpRoto)
        self.assertEqual(estado["email"], {"estado": "error", "detalle": "SMTPAuthenticationError"})


if __name__ == "__main__":
    unittest.main()
