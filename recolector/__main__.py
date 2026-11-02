"""Corrida diaria: tipos de cambio, precios por viaje activo y estado."""
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from recolector import red, tipos_cambio
from recolector.almacen import agregar_observacion, escribir_json, leer_json
from recolector.fuentes import travelpayouts

MAX_ERRORES = 20


def ejecutar(raiz: Path, get_json, ahora: datetime, token: str | None) -> dict:
    raiz = Path(raiz)
    hoy = ahora.date()
    capturado = ahora.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    viajes = leer_json(raiz / "config/viajes.json", {"viajes": []})["viajes"]
    errores = leer_json(raiz / "data/estado.json", {}).get("errores", [])

    ruta_historial = raiz / "data/tipos_cambio.json"
    historial = leer_json(ruta_historial, {})
    tasas, fuente_tasas = tipos_cambio.obtener(get_json, historial)
    if fuente_tasas in ("mindicador", "er-api"):
        historial[hoy.isoformat()] = tasas
        escribir_json(ruta_historial, historial)

    fuente = {"estado": "ok", "detalle": ""}
    if not token:
        fuente = {"estado": "error", "detalle": "falta TRAVELPAYOUTS_TOKEN"}
    cobertura = {}
    for viaje in viajes:
        if not viaje.get("activo") or not token or not travelpayouts.consultas(viaje, hoy):
            continue
        try:
            lista, cobertura[viaje["id"]] = travelpayouts.recolectar(viaje, get_json, token, hoy, capturado, tasas)
            if lista:
                agregar_observacion(raiz, viaje["id"], min(lista, key=lambda o: o["precio"]["monto"]))
        except Exception as e:  # un viaje roto no debe tumbar la corrida
            traceback.print_exc()
            fuente = {"estado": "error", "detalle": str(e)}
            errores.append({"fecha": capturado, "fuente": "travelpayouts", "viaje_id": viaje["id"], "mensaje": str(e)})

    estado = {
        "ultima_corrida": capturado,
        "tipos_cambio": fuente_tasas,
        "fuentes": {"travelpayouts": fuente},
        "viajes": cobertura,
        "errores": errores[-MAX_ERRORES:],
    }
    escribir_json(raiz / "data/estado.json", estado)
    return estado


def main() -> int:
    estado = ejecutar(Path.cwd(), red.get_json, datetime.now(timezone.utc), os.environ.get("TRAVELPAYOUTS_TOKEN"))
    print(f"Tipos de cambio: {estado['tipos_cambio']} · Travelpayouts: {estado['fuentes']['travelpayouts']}")
    for viaje_id, c in estado["viajes"].items():
        print(f"{viaje_id}: {c['ofertas']} ofertas, {c['fechas_con_precio']}/{c['fechas_posibles']} fechas con precio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
