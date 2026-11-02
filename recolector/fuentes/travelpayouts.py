"""Travelpayouts Data API: precios cacheados (2-7 días) de búsquedas ajenas; el precio viene por persona."""
import calendar
from datetime import date, timedelta

from recolector.red import ErrorRed
from recolector.tipos_cambio import a_clp

URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def _ventana(viaje: dict) -> tuple[date, date]:
    """Rango de fechas de salida aceptadas para el viaje."""
    f = viaje["fechas"]
    if f["modo"] == "fija":
        salida = date.fromisoformat(f["salida"])
        return salida, salida
    if f["modo"] == "flexible":
        salida, margen = date.fromisoformat(f["salida"]), timedelta(days=f["margen_dias"])
        return salida - margen, salida + margen
    anio, mes = map(int, f["mes"].split("-"))
    return date(anio, mes, 1), date(anio, mes, calendar.monthrange(anio, mes)[1])


def consultas(viaje: dict, hoy: date) -> list[dict]:
    inicio, fin = _ventana(viaje)
    inicio = max(inicio, hoy)
    if fin < inicio:
        return []
    ida_vuelta = viaje["tipo"] == "ida_vuelta"
    base = {
        "origin": viaje["origen"],
        "destination": viaje["destino"],
        "one_way": "false" if ida_vuelta else "true",
        "currency": "usd",
        "sorting": "price",
        "direct": "false",
        "limit": 1000,
    }
    f = viaje["fechas"]
    if f["modo"] == "fija":
        params = {**base, "departure_at": f["salida"]}
        if ida_vuelta:
            params["return_at"] = f["regreso"]
        return [params]
    meses = []
    dia = inicio.replace(day=1)
    while dia <= fin:
        meses.append({**base, "departure_at": dia.strftime("%Y-%m")})
        dia = (dia + timedelta(days=32)).replace(day=1)
    return meses


def ofertas(resp: dict, viaje: dict, hoy: date, capturado: str, tasas: dict | None) -> list[dict]:
    inicio, fin = _ventana(viaje)
    ida_vuelta = viaje["tipo"] == "ida_vuelta"
    moneda = str(resp.get("currency") or "usd").upper()
    resultado = []
    for item in resp.get("data") or []:
        if item.get("price") is None or not item.get("departure_at"):
            continue
        salida = item["departure_at"][:10]
        regreso = (item.get("return_at") or "")[:10] or None
        d_salida = date.fromisoformat(salida)
        if d_salida < hoy or not inicio <= d_salida <= fin:
            continue
        if ida_vuelta:
            if regreso is None:
                continue
            estadia = (date.fromisoformat(regreso) - d_salida).days
            minimo, maximo = viaje["estadia_dias"]
            if viaje["fechas"]["modo"] != "fija" and not minimo <= estadia <= maximo:
                continue
        monto = round(item["price"] * viaje["pasajeros"], 2)
        resultado.append({
            "capturado": capturado,
            "fuente": "travelpayouts",
            "salida": salida,
            "regreso": regreso if ida_vuelta else None,
            "origen": item.get("origin_airport") or viaje["origen"],
            "destino": item.get("destination_airport") or viaje["destino"],
            "precio": {"monto": monto, "moneda": moneda, "clp": a_clp(monto, moneda, tasas)},
            "escalas": max(item.get("transfers") or 0, item.get("return_transfers") or 0),
            "duracion_min": item.get("duration"),
            "aerolineas": [item["airline"]] if item.get("airline") else [],
            "self_transfer": False,
            "tramos": [],
            "enlace": "https://www.aviasales.com" + item["link"] if item.get("link") else None,
        })
    return resultado


def cobertura(lista: list[dict], viaje: dict, hoy: date) -> dict:
    inicio, fin = _ventana(viaje)
    posibles = max((fin - max(inicio, hoy)).days + 1, 0)
    return {"ofertas": len(lista), "fechas_con_precio": len({o["salida"] for o in lista}), "fechas_posibles": posibles}


def recolectar(viaje: dict, get_json, token: str, hoy: date, capturado: str, tasas: dict | None) -> tuple[list[dict], dict]:
    lista = []
    for params in consultas(viaje, hoy):
        resp = get_json(URL, params, headers={"X-Access-Token": token})
        if not resp.get("success"):
            raise ErrorRed(f"Travelpayouts: {resp.get('error') or 'respuesta sin success'}")
        lista.extend(ofertas(resp, viaje, hoy, capturado, tasas))
    return lista, cobertura(lista, viaje, hoy)
