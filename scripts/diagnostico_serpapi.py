"""Diagnóstico temporal: cuota y forma real de la respuesta de SerpApi Google Flights (no imprime la clave)."""
import os
from datetime import datetime, timezone

from recolector import red

clave = os.environ["SERPAPI_KEY"]
cuenta = red.get_json("https://serpapi.com/account", {"api_key": clave})
print("cuenta:", {k: cuenta.get(k) for k in ("plan_name", "searches_per_month", "plan_searches_left", "this_month_usage", "account_rate_limit_per_hour")})

r = red.get_json("https://serpapi.com/search.json", {
    "engine": "google_flights", "departure_id": "SCL", "arrival_id": "FRA",
    "outbound_date": "2027-03-08", "return_date": "2027-03-24", "type": "1",
    "currency": "USD", "hl": "es", "gl": "cl", "api_key": clave,
})
print("claves:", sorted(r.keys()))
print("estado:", r.get("search_metadata", {}).get("status"), "| error:", r.get("error"))
for grupo in ("best_flights", "other_flights"):
    lista = r.get(grupo) or []
    print(f"{grupo}: {len(lista)} itinerarios, precios {[x.get('price') for x in lista][:6]}")
if r.get("best_flights"):
    x = r["best_flights"][0]
    print("claves itinerario:", sorted(x.keys()))
    print("tramos:", [(f["departure_airport"]["id"], f["arrival_airport"]["id"], f["departure_airport"]["time"], f.get("airline")) for f in x["flights"]])
    print("total_duration:", x.get("total_duration"), "| layovers:", [(l.get("id"), l.get("duration"), l.get("overnight")) for l in x.get("layovers", [])])
pi = r.get("price_insights") or {}
print("price_insights claves:", sorted(pi.keys()))
print("lowest_price:", pi.get("lowest_price"), "| price_level:", pi.get("price_level"), "| typical_price_range:", pi.get("typical_price_range"))
hist = pi.get("price_history") or []
print("price_history:", len(hist), "puntos")
for ts, precio in hist[:2] + hist[-2:]:
    print("   ", datetime.fromtimestamp(ts, timezone.utc).date(), precio)
