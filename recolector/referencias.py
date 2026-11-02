"""Qué par de fechas sigue cada viaje a diario, cuándo rehacer el calendario y la cuota de SerpApi."""
from datetime import date, datetime, timedelta


def fechas_referencia(viaje: dict, guardadas: dict, calendario: dict | None, hoy: date) -> tuple[str, str | None, str] | None:
    fechas = viaje["fechas"]
    if fechas["modo"] == "fija":
        return fechas["salida"], fechas.get("regreso"), "fija"
    desde = hoy.isoformat()
    for ref, origen in ((viaje.get("referencia"), "usuario"), (guardadas.get(viaje["id"]), "guardada")):
        if ref and ref["salida"] >= desde:  # una referencia ya pasada no se consulta
            return ref["salida"], ref.get("regreso"), origen
    if not (calendario or {}).get("completo"):
        return None  # un calendario parcial no debe fijar una referencia que luego no cambia
    opciones = {s: v for s, v in calendario.get("fechas", {}).items() if s >= desde}
    if not opciones:
        return None
    salida = min(opciones, key=lambda s: opciones[s]["monto"])
    return salida, opciones[salida].get("regreso"), "calendario"


def calendario_vencido(calendario: dict | None, ahora: datetime, dias: int = 7) -> bool:
    if not calendario or not calendario.get("generado") or not calendario.get("completo"):
        return True
    generado = datetime.fromisoformat(calendario["generado"].replace("Z", "+00:00"))
    return ahora - generado > timedelta(days=dias)


def uso_serpapi(previo: dict | None, ahora: datetime) -> dict:
    mes = ahora.strftime("%Y-%m")
    if not previo or previo.get("mes") != mes:
        return {"mes": mes, "usadas": 0}
    return {"mes": mes, "usadas": previo.get("usadas", 0)}
