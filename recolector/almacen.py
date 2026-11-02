"""Lectura y escritura de los JSON versionados en el repo."""
import json
import os
from pathlib import Path
from typing import Any


def leer_json(ruta: Path, defecto: Any) -> Any:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defecto


def escribir_json(ruta: Path, datos: Any) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporal, ruta)


def agregar_observacion(raiz: Path, viaje_id: str, obs: dict) -> bool:
    """Guarda obs en el archivo mensual; por fuente y día queda solo la de menor monto."""
    ruta = Path(raiz) / "data" / "precios" / viaje_id / f"{obs['capturado'][:7]}.json"
    datos = leer_json(ruta, {"viaje_id": viaje_id, "observaciones": []})
    lista = datos["observaciones"]
    dia = obs["capturado"][:10]
    for i, previa in enumerate(lista):
        if previa["fuente"] == obs["fuente"] and previa["capturado"][:10] == dia:
            if obs["precio"]["monto"] >= previa["precio"]["monto"]:
                return False
            lista[i] = obs
            break
    else:
        lista.append(obs)
    escribir_json(ruta, datos)
    return True
