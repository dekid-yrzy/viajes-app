"""Diagnóstico temporal: conteos crudos de Travelpayouts por variante de consulta (no imprime el token)."""
import collections
import os
from datetime import date

from recolector import red
from recolector.fuentes.travelpayouts import URL
from recolector.tipos_cambio import MINDICADOR_URL

token = os.environ["TRAVELPAYOUTS_TOKEN"]
try:
    red.get_json(MINDICADOR_URL)
    print("mindicador: ok")
except Exception as e:
    print(f"mindicador: {type(e).__name__}: {e} (estado={getattr(e, 'estado', None)})")

variantes = {
    "ida_vuelta mes": {"departure_at": "2027-03", "one_way": "false"},
    "ida_vuelta mes+regreso mes": {"departure_at": "2027-03", "return_at": "2027-03", "one_way": "false"},
    "ida_vuelta mes+regreso abr": {"departure_at": "2027-03", "return_at": "2027-04", "one_way": "false"},
    "solo ida mes": {"departure_at": "2027-03", "one_way": "true"},
    "ida_vuelta sin fecha": {"one_way": "false"},
    "solo ida sin fecha": {"one_way": "true"},
}
for destino in ("FRA", "MAD", "NRT", "PAR", "LON", "TYO"):
    for nombre, extra in variantes.items():
        params = {"origin": "SCL", "destination": destino, "currency": "usd", "sorting": "price", "direct": "false", "limit": 1000, **extra}
        try:
            data = red.get_json(URL, params, headers={"X-Access-Token": token}).get("data") or []
        except Exception as e:
            print(f"{destino} | {nombre}: {type(e).__name__}: {e}")
            continue
        salidas = sorted({d["departure_at"][:10] for d in data if d.get("departure_at")})
        estadias = collections.Counter(
            (date.fromisoformat(d["return_at"][:10]) - date.fromisoformat(d["departure_at"][:10])).days
            for d in data if d.get("return_at") and d.get("departure_at")
        )
        rango = f"{salidas[0]}..{salidas[-1]}" if salidas else "-"
        print(f"{destino} | {nombre}: {len(data)} ofertas, {len(salidas)} salidas ({rango}), estadías {sorted(estadias.items())[:12]}")
