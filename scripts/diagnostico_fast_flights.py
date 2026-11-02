"""Diagnóstico temporal: ¿fast-flights funciona desde GitHub Actions para rutas desde SCL?"""
import time

from fast_flights import FlightData, Passengers, get_flights

consultas = [("FRA", "2027-03-08", "2027-03-24"), ("MAD", "2027-03-08", "2027-03-24"), ("NRT", "2027-03-15", "2027-03-31"), ("FRA", "2027-03-15", "2027-03-31")]
for destino, ida, vuelta in consultas:
    inicio = time.time()
    try:
        r = get_flights(
            flight_data=[FlightData(date=ida, from_airport="SCL", to_airport=destino), FlightData(date=vuelta, from_airport=destino, to_airport="SCL")],
            trip="round-trip",
            seat="economy",
            passengers=Passengers(adults=1),
            fetch_mode="common",  # no "fallback": enviaría la consulta a un servicio de terceros
        )
        precios = [f.price for f in r.flights][:5]
        print(f"{destino} {ida}->{vuelta}: {len(r.flights)} vuelos, nivel={r.current_price!r}, primeros precios={precios}, {time.time() - inicio:.1f}s")
        if r.flights:
            f = r.flights[0]
            print(f"   ejemplo: {f.name} | {f.departure} -> {f.arrival} | {f.duration} | escalas={f.stops}")
    except Exception as e:
        print(f"{destino} {ida}->{vuelta}: {type(e).__name__}: {str(e)[:300]}")
    time.sleep(5)
