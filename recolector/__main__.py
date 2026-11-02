"""Corrida diaria: tipos de cambio, precios por viaje activo y estado."""
import os
import smtplib
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from recolector import alertas, notificar, red, tipos_cambio
from recolector.almacen import agregar_observacion, escribir_json, leer_json
from recolector.fuentes import google_flights, serpapi, travelpayouts
from recolector.referencias import calendario_vencido, fechas_referencia, uso_serpapi

MAX_ERRORES = 20
MAX_ALERTAS = 200


def _leer_tolerante(ruta: Path, defecto):
    """Archivos de estado: si están corruptos se regeneran desde cero."""
    try:
        return leer_json(ruta, defecto)
    except ValueError:
        return defecto


def ejecutar(
    raiz: Path, get_json, ahora: datetime, claves: dict, buscar=None, pausa: float = 2.0,
    entorno: dict | None = None, post_json=None, smtp_factory=None,
) -> dict:
    raiz = Path(raiz)
    hoy = ahora.date()
    capturado = ahora.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    previo = _leer_tolerante(raiz / "data/estado.json", {})
    errores = previo.get("errores", [])
    try:
        viajes = leer_json(raiz / "config/viajes.json", {"viajes": []})["viajes"]
    except (ValueError, KeyError, TypeError) as e:
        viajes = []
        errores.append({"fecha": capturado, "fuente": "config", "viaje_id": None, "mensaje": f"config/viajes.json inválido: {e}"})
    ajustes = _leer_tolerante(raiz / "config/ajustes.json", {})
    limite_serpapi = ajustes.get("serpapi_presupuesto_mensual", 200)
    uso = uso_serpapi(previo.get("serpapi_uso"), ahora)
    ruta_referencias = raiz / "data/referencias.json"
    guardadas = _leer_tolerante(ruta_referencias, {})

    ruta_historial = raiz / "data/tipos_cambio.json"
    historial = _leer_tolerante(ruta_historial, {})
    tasas, fuente_tasas = tipos_cambio.obtener(get_json, historial)
    if fuente_tasas in ("mindicador", "er-api"):
        historial[hoy.isoformat()] = tasas
        escribir_json(ruta_historial, historial)

    token, clave_serpapi = claves.get("travelpayouts"), claves.get("serpapi")
    fuentes = {
        "travelpayouts": {"estado": "ok", "detalle": ""} if token else {"estado": "error", "detalle": "falta TRAVELPAYOUTS_TOKEN"},
        "serpapi": {"estado": "ok", "detalle": ""} if clave_serpapi else {"estado": "sin_clave", "detalle": "falta SERPAPI_KEY"},
        "fast_flights": {"estado": "ok", "detalle": ""} if buscar else {"estado": "desactivado", "detalle": ""},
    }

    def registrar(fuente: str, viaje_id, mensaje: str) -> None:
        if fuente in fuentes:
            fuentes[fuente] = {"estado": "error", "detalle": mensaje}
        errores.append({"fecha": capturado, "fuente": fuente, "viaje_id": viaje_id, "mensaje": mensaje})

    def en_vivo(viaje: dict) -> dict:
        vid = viaje["id"]
        ruta_cal = raiz / f"data/calendario/{vid}.json"
        cal = _leer_tolerante(ruta_cal, None)
        if buscar and viaje["fechas"]["modo"] != "fija" and calendario_vencido(cal, ahora):
            try:
                nuevo = google_flights.calendario(viaje, hoy, buscar, capturado, tasas, pausa)
            except Exception as e:
                nuevo = None
                registrar("fast_flights", vid, str(e))
            else:
                if not nuevo:
                    registrar("fast_flights", vid, "calendario sin precios")
            if nuevo:
                cal = nuevo
                escribir_json(ruta_cal, cal)
        ref = fechas_referencia(viaje, guardadas, cal, hoy)
        if ref is None:
            registrar("referencia", vid, "sin fechas de referencia")
            return {}
        salida, regreso, origen = ref
        if origen == "calendario":
            guardadas[vid] = {"salida": salida, "regreso": regreso}
            escribir_json(ruta_referencias, guardadas)

        resultado = {"referencia": {"salida": salida, "regreso": regreso, "origen": origen}, "fuente_en_vivo": None}
        ruta_google = raiz / f"data/historial_google/{vid}.json"
        anterior = _leer_tolerante(ruta_google, {})
        if clave_serpapi and anterior.get("actualizado", "")[:10] == capturado[:10] and (anterior.get("salida"), anterior.get("regreso")) == (salida, regreso):
            return {**resultado, "fuente_en_vivo": "serpapi"}  # ya consultado hoy: no repetir gasto ni scraping

        obs, fuente_vivo = None, None
        if clave_serpapi:
            if uso["usadas"] >= limite_serpapi:
                fuentes["serpapi"] = {"estado": "cuota_agotada", "detalle": f"{uso['usadas']}/{limite_serpapi} en {uso['mes']}"}
            else:
                uso["usadas"] += 1  # se cuenta antes de llamar: una llamada fallida también puede gastar cuota
                try:
                    obs, puntos = serpapi.consultar(viaje, salida, regreso, get_json, clave_serpapi, capturado, tasas)
                    if obs:
                        # Google solo entrega 61 días: se acumulan para no olvidar mínimos más antiguos
                        acumulados = dict(anterior.get("puntos") or []) if (anterior.get("salida"), anterior.get("regreso")) == (salida, regreso) else {}
                        acumulados.update(dict(puntos))
                        escribir_json(ruta_google, {"salida": salida, "regreso": regreso, "actualizado": capturado, "puntos": sorted([list(p) for p in acumulados.items()])})
                except Exception as e:
                    traceback.print_exc()
                    registrar("serpapi", vid, str(e))
            fuente_vivo = "serpapi" if obs else None
        if obs is None and buscar:
            try:
                obs = google_flights.observacion(buscar(viaje, salida, regreso), viaje, salida, regreso, capturado, tasas)
                fuente_vivo = "fast_flights" if obs else None
            except Exception as e:
                traceback.print_exc()
                registrar("fast_flights", vid, str(e))
        if obs:
            agregar_observacion(raiz, vid, obs)
        return {**resultado, "fuente_en_vivo": fuente_vivo}

    resumen = {}
    for viaje in viajes:
        if not viaje.get("activo"):
            continue
        vid = viaje.get("id")
        try:  # un viaje roto no debe tumbar la corrida
            if not travelpayouts.consultas(viaje, hoy):
                continue
        except Exception as e:
            traceback.print_exc()
            registrar("config", vid, str(e))
            continue
        info = {}
        if token:
            try:
                lista, cobertura = travelpayouts.recolectar(viaje, get_json, token, hoy, capturado, tasas)
                info.update(cobertura)
                if lista:
                    agregar_observacion(raiz, vid, min(lista, key=lambda o: o["precio"]["monto"]))
            except Exception as e:
                traceback.print_exc()
                registrar("travelpayouts", vid, str(e))
        if clave_serpapi or buscar:
            try:
                info.update(en_vivo(viaje))
            except Exception as e:
                traceback.print_exc()
                registrar("en_vivo", vid, str(e))
        if info:
            resumen[vid] = info

    nuevas = []
    sin_envio = {"estado": "sin_alertas" if entorno is not None else "desactivado", "detalle": ""}
    fuentes["telegram"], fuentes["email"] = dict(sin_envio), dict(sin_envio)
    try:
        ruta_alertas = raiz / "data/alertas.json"
        previas = _leer_tolerante(ruta_alertas, {}).get("alertas", [])
        hoy_iso = hoy.isoformat()
        candidatas, por_id = [], {}
        for viaje in viajes:
            vid = viaje.get("id")
            if not viaje.get("activo") or vid not in resumen:
                continue
            por_id[vid] = viaje
            observaciones = []
            for archivo in sorted((raiz / "data/precios" / vid).glob("*.json")):
                observaciones += _leer_tolerante(archivo, {}).get("observaciones", [])
            ref = resumen[vid].get("referencia")
            serie = []
            if ref:
                historial = _leer_tolerante(raiz / f"data/historial_google/{vid}.json", None)
                serie = alertas.serie_en_vivo(historial, observaciones, ref["salida"], ref["regreso"])
            obs_hoy = [o for o in observaciones if o["capturado"][:10] == hoy_iso]
            candidatas += alertas.evaluar(viaje, hoy_iso, obs_hoy, serie, ajustes, tasas)
        entorno_ = entorno or {}
        hay_canal = bool(
            (entorno_.get("TELEGRAM_BOT_TOKEN") and entorno_.get("TELEGRAM_CHAT_ID"))
            or (entorno_.get("SMTP_USER") and entorno_.get("SMTP_PASSWORD") and entorno_.get("EMAIL_DESTINO"))
        )
        # una alerta que quedó solo en la app (canales caídos o sin configurar) se reintenta cuando hay un canal
        previas_vigentes = [p for p in previas if not (hay_canal and p.get("canales_enviados") == ["app"])]
        nuevas = alertas.suprimir(candidatas, previas_vigentes, hoy_iso)
        if nuevas:
            canales = ["app"]
            if entorno is not None:
                texto = alertas.mensaje(nuevas, por_id, ajustes.get("url_publica", ""))
                envio = notificar.enviar(texto, f"Viajes: {len(nuevas)} alerta(s) de precio", entorno, post_json, smtp_factory)
                fuentes.update(envio)
                canales = [c for c in ("telegram", "email") if envio[c]["estado"] == "ok"] + canales
            for a in nuevas:
                a.update({"id": f"{a['viaje_id']}-{a['tipo']}-{capturado}", "fecha": capturado, "canales_enviados": canales})
            escribir_json(ruta_alertas, {"alertas": (previas + nuevas)[-MAX_ALERTAS:]})
    except Exception as e:  # una alerta rota no debe perder los precios ya guardados
        traceback.print_exc()
        registrar("alertas", None, f"{type(e).__name__}: {e}")
        nuevas = []

    estado = {
        "ultima_corrida": capturado,
        "tipos_cambio": fuente_tasas,
        "fuentes": fuentes,
        "serpapi_uso": uso,
        "viajes": resumen,
        "alertas_nuevas": len(nuevas),
        "errores": errores[-MAX_ERRORES:],
    }
    escribir_json(raiz / "data/estado.json", estado)
    return estado


def main() -> int:
    claves = {"travelpayouts": os.environ.get("TRAVELPAYOUTS_TOKEN"), "serpapi": os.environ.get("SERPAPI_KEY")}
    buscar = None if os.environ.get("DESACTIVAR_FAST_FLIGHTS") == "1" else google_flights.buscar
    estado = ejecutar(
        Path.cwd(), red.get_json, datetime.now(timezone.utc), claves, buscar=buscar,
        entorno=dict(os.environ), post_json=red.post_json, smtp_factory=smtplib.SMTP_SSL,
    )
    print(f"Tipos de cambio: {estado['tipos_cambio']} · SerpApi: {estado['serpapi_uso']['usadas']} usadas en {estado['serpapi_uso']['mes']}")
    for nombre, fuente in estado["fuentes"].items():
        print(f"  {nombre}: {fuente['estado']} {fuente['detalle']}")
    for viaje_id, info in estado["viajes"].items():
        print(f"{viaje_id}: {info}")
    print(f"Alertas nuevas: {estado['alertas_nuevas']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
