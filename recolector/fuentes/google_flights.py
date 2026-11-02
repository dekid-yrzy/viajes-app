"""Google Flights vía fast-flights (scraping, contra los términos de Google): respaldo y calendario semanal."""
import re
import time
from datetime import date, timedelta

from recolector.fuentes.travelpayouts import ventana
from recolector.tipos_cambio import a_clp

_PRECIO_USD = re.compile(r"^\$(\d[\d,]*)$")


def buscar(viaje: dict, salida: str, regreso: str | None):
    from fast_flights import FlightData, Passengers, get_flights  # import perezoso: dependencia solo de runtime

    tramos = [FlightData(date=salida, from_airport=viaje["origen"], to_airport=viaje["destino"])]
    if regreso:
        tramos.append(FlightData(date=regreso, from_airport=viaje["destino"], to_airport=viaje["origen"]))
    return get_flights(
        flight_data=tramos,
        trip="round-trip" if regreso else "one-way",
        seat="economy",
        passengers=Passengers(adults=viaje["pasajeros"]),
        fetch_mode="common",  # "fallback" enviaría la consulta a un servicio de terceros
    )


def precio_usd(texto) -> int | None:
    # shortcut: solo entiende "$1,043" (USD desde IPs de EE.UU.); otra moneda se descarta, no se convierte
    coincidencia = _PRECIO_USD.match(texto.strip()) if isinstance(texto, str) else None
    return int(coincidencia.group(1).replace(",", "")) if coincidencia else None


def observacion(resultado, viaje: dict, salida: str, regreso: str | None, capturado: str, tasas: dict | None) -> dict | None:
    validos = [(precio_usd(v.price), v) for v in getattr(resultado, "flights", None) or []]
    validos = [(p, v) for p, v in validos if p]
    if not validos:
        return None
    precio, mejor = min(validos, key=lambda x: x[0])
    monto = float(precio)
    return {
        "capturado": capturado,
        "fuente": "fast_flights",
        "salida": salida,
        "regreso": regreso,
        "origen": viaje["origen"],
        "destino": viaje["destino"],
        "precio": {"monto": monto, "moneda": "USD", "clp": a_clp(monto, "USD", tasas)},
        "escalas": mejor.stops if isinstance(mejor.stops, int) else 0,
        "duracion_min": None,
        "aerolineas": [a for a in (mejor.name or "").split(", ") if a],
        "self_transfer": False,
        "tramos": [],
        "enlace": None,
        "nivel": getattr(resultado, "current_price", None),
    }


def estadia_calendario(viaje: dict) -> int | None:
    if viaje["tipo"] != "ida_vuelta":
        return None
    minimo, maximo = viaje["estadia_dias"]
    return (minimo + maximo) // 2


def calendario(viaje: dict, hoy: date, buscar_fn, generado: str, tasas: dict | None, pausa: float = 2.0) -> dict | None:
    inicio, fin = ventana(viaje)
    estadia = estadia_calendario(viaje)
    fechas, errores = {}, 0
    dia = max(inicio, hoy)
    while dia <= fin:
        salida = dia.isoformat()
        regreso = (dia + timedelta(days=estadia)).isoformat() if estadia is not None else None
        try:
            obs = observacion(buscar_fn(viaje, salida, regreso), viaje, salida, regreso, generado, tasas)
        except Exception:  # un bloqueo o cambio de formato en una fecha no debe perder las demás
            obs, errores = None, errores + 1
        if obs:
            fechas[salida] = {"regreso": regreso, "monto": obs["precio"]["monto"], "clp": obs["precio"]["clp"], "nivel": obs["nivel"]}
        dia += timedelta(days=1)
        if pausa and dia <= fin:
            time.sleep(pausa)
    if not fechas:
        return None
    return {"generado": generado, "estadia_dias": estadia, "fechas": fechas, "errores": errores}
