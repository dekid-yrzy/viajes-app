import json
from pathlib import Path

from recolector.red import ErrorRed

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(nombre):
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


def siempre_falla(url, params=None, headers=None, timeout=30):
    raise ErrorRed("caído", estado=503)
