"""Detección de oportunidades de compra y regla anti-repetición (SPEC 4.1 y 4.4)."""
import statistics
from datetime import date, timedelta

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic"]
EN_VIVO = ("serpapi", "fast_flights")
MARGEN_MINIMO = 0.02  # un "nuevo mínimo" por US$1 en una ruta que va bajando sería spam


def clp(valor: int | None) -> str:
    return "—" if valor is None else "CLP " + f"{round(valor):,}".replace(",", ".")


def usd(valor: float) -> str:
    entero, decimales = f"{valor:,.2f}".split(".")
    return f"US${entero.replace(',', '.')},{decimales}"


def fecha_corta(iso: str | None) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


def serie_en_vivo(historial: dict | None, observaciones: list[dict], salida: str, regreso: str | None) -> list[tuple[str, float]]:
    """Misma regla que serieGoogle en js/datos.js: historial de Google + observaciones en vivo de la referencia."""
    por_fecha = {}
    if historial and historial.get("salida") == salida and historial.get("regreso") == regreso:
        for fecha, precio in historial.get("puntos") or []:
            por_fecha[fecha] = precio
    for o in observaciones:
        if o["fuente"] in EN_VIVO and o.get("salida") == salida and o.get("regreso") == regreso:
            por_fecha[o["capturado"][:10]] = o["precio"]["monto"]
    return sorted(por_fecha.items())


def _extras(viaje: dict) -> int:
    return (viaje.get("equipaje") or {}).get("costo_estimado_clp", 0) + (viaje.get("traslados_clp") or 0)


def _alerta(viaje, tipo, fuente, precio_usd, precio_clp, referencia_usd, referencia_clp, salida, regreso, motivo) -> dict:
    return {
        "viaje_id": viaje["id"],
        "tipo": tipo,
        "fuente": fuente,
        "precio_usd": precio_usd,
        "precio_clp": precio_clp,
        "referencia_usd": referencia_usd,
        "referencia_clp": referencia_clp,
        "costo_total_clp": None if precio_clp is None else precio_clp + _extras(viaje),
        "salida": salida,
        "regreso": regreso,
        "motivo": motivo,
    }


def evaluar(viaje: dict, hoy: str, obs_hoy: list[dict], serie: list[tuple[str, float]], ajustes: dict, tasas: dict | None) -> list[dict]:
    alertas = []
    umbral = viaje.get("umbral_clp")
    con_clp = [o for o in obs_hoy if o["precio"].get("clp") is not None]
    if umbral and con_clp:
        o = min(con_clp, key=lambda x: x["precio"]["clp"])
        costo = o["precio"]["clp"] + _extras(viaje)
        if costo <= umbral:
            alertas.append(_alerta(
                viaje, "umbral", o["fuente"], o["precio"]["monto"], o["precio"]["clp"], None, umbral, o.get("salida"), o.get("regreso"),
                f"Costo total {clp(costo)} bajo tu umbral de {clp(umbral)}",
            ))

    if not serie or serie[-1][0] != hoy:
        return alertas
    precio, previos = serie[-1][1], serie[:-1]
    tasa_usd = (tasas or {}).get("USD")
    a_clp = (lambda v: round(v * tasa_usd)) if tasa_usd else (lambda v: None)
    vivo = [o for o in obs_hoy if o["fuente"] in EN_VIVO]
    salida, regreso = (vivo[-1].get("salida"), vivo[-1].get("regreso")) if vivo else (None, None)

    desde = (date.fromisoformat(hoy) - timedelta(days=7)).isoformat()
    semana = [v for f, v in previos if f >= desde]
    pct = ajustes.get("caida_pct_alerta", 10)
    if len(semana) >= 3:
        mediana = statistics.median(semana)
        if precio <= mediana * (1 - pct / 100):
            baja = round((1 - precio / mediana) * 100)
            alertas.append(_alerta(
                viaje, "caida_pct", "en_vivo", precio, a_clp(precio), mediana, a_clp(mediana), salida, regreso,
                f"Bajó {baja} % respecto de la mediana de 7 días ({usd(mediana)} → {usd(precio)})",
            ))
    if len(previos) >= ajustes.get("min_observaciones_percentil", 14):
        minimo = min(v for _, v in previos)
        if precio <= minimo * (1 - MARGEN_MINIMO):
            alertas.append(_alerta(
                viaje, "minimo_historico", "en_vivo", precio, a_clp(precio), minimo, a_clp(minimo), salida, regreso,
                f"Nuevo mínimo histórico: {usd(precio)} (antes {usd(minimo)}, {len(previos)} días de historia)",
            ))
    return alertas


def suprimir(candidatas: list[dict], previas: list[dict], hoy: str) -> list[dict]:
    dia = date.fromisoformat(hoy)
    nuevas = []
    for c in candidatas:
        recientes = [
            p for p in previas
            if p.get("viaje_id") == c["viaje_id"] and p.get("tipo") == c["tipo"]
            and (dia - date.fromisoformat(p["fecha"][:10])).days < 3
        ]
        ultima = max(recientes, key=lambda p: p["fecha"], default=None)
        if ultima is None or c["precio_usd"] <= ultima["precio_usd"] * 0.95:
            nuevas.append(c)
    return nuevas


def mensaje(alertas: list[dict], viajes: dict[str, dict], url: str) -> str:
    bloques = []
    for viaje_id in dict.fromkeys(a["viaje_id"] for a in alertas):
        viaje = viajes[viaje_id]
        propias = [a for a in alertas if a["viaje_id"] == viaje_id]
        primera = propias[0]
        fechas = f"{fecha_corta(primera['salida'])} → {fecha_corta(primera['regreso'])}" if primera.get("regreso") else fecha_corta(primera.get("salida"))
        lineas = [f"{viaje['origen']} → {viaje['destino']}" + (f" ({fechas})" if fechas else "")]
        lineas += [f"• {a['motivo']}" for a in propias]
        lineas.append(f"Costo total estimado: {clp(min((a['costo_total_clp'] for a in propias if a['costo_total_clp'] is not None), default=None))}")
        lineas.append(f"{url}#/viaje/{viaje_id}")
        bloques.append("\n".join(lineas))
    return "\n\n".join(bloques)
