"""Tipos de cambio a CLP: mindicador.cl, con open.er-api.com e historial como respaldo."""
from recolector.red import ErrorRed

MINDICADOR_URL = "https://mindicador.cl/api"
ER_API_URL = "https://open.er-api.com/v6/latest/USD"


def _validar(tasas: dict) -> dict:
    for moneda, valor in tasas.items():
        if not isinstance(valor, (int, float)) or valor <= 0:
            raise ValueError(f"tasa inválida para {moneda}: {valor!r}")
    return tasas


def desde_mindicador(resp: dict) -> dict:
    try:
        return _validar({"USD": resp["dolar"]["valor"], "EUR": resp["euro"]["valor"]})
    except (KeyError, TypeError) as e:
        raise ValueError(f"respuesta de mindicador inesperada: {e}") from e


def desde_er_api(resp: dict) -> dict:
    if resp.get("result") != "success":
        raise ValueError("open.er-api.com no respondió success")
    try:
        tasas = resp["rates"]
        _validar({"CLP": tasas["CLP"], "EUR": tasas["EUR"]})
        return {"USD": round(tasas["CLP"], 2), "EUR": round(tasas["CLP"] / tasas["EUR"], 2)}
    except (KeyError, TypeError) as e:
        raise ValueError(f"respuesta de open.er-api.com inesperada: {e}") from e


def obtener(get_json, historial: dict) -> tuple[dict | None, str]:
    for nombre, url, parsear in (("mindicador", MINDICADOR_URL, desde_mindicador), ("er-api", ER_API_URL, desde_er_api)):
        try:
            return parsear(get_json(url)), nombre
        except (ErrorRed, ValueError):
            continue
    if historial:
        return historial[max(historial)], "historial"
    return None, "sin_datos"


def a_clp(monto: float, moneda: str, tasas: dict | None) -> int | None:
    if moneda == "CLP":
        return round(monto)
    if tasas is None or moneda not in tasas:
        return None
    return round(monto * tasas[moneda])
