import http.client
import unittest
from unittest import mock

from recolector.red import ErrorRed, get_json


class TestRed(unittest.TestCase):
    def test_conexion_cortada_se_convierte_en_error_red(self):
        for excepcion in (ConnectionResetError("reset"), http.client.RemoteDisconnected("cerrada"), http.client.IncompleteRead(b"")):
            with self.subTest(excepcion=type(excepcion).__name__):
                with mock.patch("urllib.request.urlopen", side_effect=excepcion):
                    with self.assertRaises(ErrorRed):
                        get_json("https://ejemplo.test")


if __name__ == "__main__":
    unittest.main()
