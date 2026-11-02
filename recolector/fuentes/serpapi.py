"""SerpApi Google Flights: precio en vivo del par de fechas de referencia, más price_insights de Google."""
from datetime import datetime, timezone

from recolector.red import ErrorRed
from recolector.tipos_cambio import a_clp

URL = "https://serpapi.com/search.json"


def parametros(viaje: dict, salida: str, regreso: str | None) -> dict:
    ida_vuelta = viaje["tipo"] == "ida_vuelta"
    params = {
        "engine": "google_flights",
        "departure_id": viaje["origen"],
        "arrival_id": viaje["destino"],
        "outbound_date": salida,
        "type": "1" if ida_vuelta else "2",
        "currency": "USD",
        "hl": "es",
        "gl": "cl",
        "adults": viaje["pasajeros"],
    }
    if ida_vuelta:
        params["return_date"] = regreso
    return params


def _precio_valido(itinerario: dict) -> bool:
    precio = itinerario.get("price")
    return isinstance(precio, int) and not isinstance(precio, bool) and precio > 0


def observacion(resp: dict, viaje: dict, salida: str, regreso: str | None, capturado: str, tasas: dict | None) -> dict | None:
    candidatos = [x for x in (resp.get("best_flights") or []) + (resp.get("other_flights") or []) if _precio_valido(x)]
    if not candidatos:
        return None
    mejor = min(candidatos, key=lambda x: x["price"])
    tramos = [
        {
            "origen": f["departure_airport"]["id"],
            "destino": f["arrival_airport"]["id"],
            "salida": f["departure_airport"]["time"],
            "llegada": f["arrival_airport"]["time"],
            "aerolinea": f.get("airline"),
            "vuelo": f.get("flight_number"),
        }
        for f in mejor.get("flights") or []
    ]
    insights = resp.get("price_insights") or {}
    monto = float(mejor["price"])
    return {
        "capturado": capturado,
        "fuente": "serpapi",
        "salida": salida,
        "regreso": regreso if viaje["tipo"] == "ida_vuelta" else None,
        "origen": viaje["origen"],
        "destino": viaje["destino"],
        "precio": {"monto": monto, "moneda": "USD", "clp": a_clp(monto, "USD", tasas)},
        "escalas": len(mejor.get("layovers") or []),
        "duracion_min": mejor.get("total_duration"),
        "aerolineas": list(dict.fromkeys(t["aerolinea"] for t in tramos if t["aerolinea"])),
        "self_transfer": False,
        "tramos": tramos,
        "enlace": (resp.get("search_metadata") or {}).get("google_flights_url"),
        "nivel": insights.get("price_level"),
        "rango_tipico": insights.get("typical_price_range"),
    }


def historial(resp: dict) -> list[list]:
    puntos = []
    for punto in (resp.get("price_insights") or {}).get("price_history") or []:
        try:
            marca, precio = punto
            puntos.append([datetime.fromtimestamp(marca, timezone.utc).date().isoformat(), precio])
        except (TypeError, ValueError, OverflowError, OSError):
            continue
    return sorted(puntos)


def consultar(viaje: dict, salida: str, regreso: str | None, get_json, clave: str, capturado: str, tasas: dict | None) -> tuple[dict | None, list[list]]:
    resp = get_json(URL, {**parametros(viaje, salida, regreso), "api_key": clave})
    if resp.get("error"):
        raise ErrorRed(f"SerpApi: {resp['error']}")
    return observacion(resp, viaje, salida, regreso, capturado, tasas), historial(resp)
