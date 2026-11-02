// Transformaciones puras de los JSON del recolector a series y montos para la UI.

export function tasaPara(tiposCambio, fecha) {
  const fechas = Object.keys(tiposCambio || {}).sort();
  if (!fechas.length) return null;
  const anteriores = fechas.filter((f) => f <= fecha);
  // Los días sembrados desde Google son anteriores al primer tipo de cambio guardado: se usa el más antiguo.
  return tiposCambio[anteriores.length ? anteriores.at(-1) : fechas[0]];
}

export function convertir(usd, moneda, tasa) {
  if (moneda === "USD") return usd;
  if (!tasa) return null;
  if (moneda === "CLP") return Math.round(usd * tasa.USD);
  return Math.round((usd * tasa.USD * 100) / tasa.EUR) / 100;
}

const mismaReferencia = (a, b) => Boolean(a && b) && a.salida === b.salida && (a.regreso ?? null) === (b.regreso ?? null);

export function serieGoogle(historial, observaciones, referencia) {
  const porFecha = new Map();
  if (mismaReferencia(historial, referencia)) {
    for (const [fecha, usd] of historial.puntos || []) porFecha.set(fecha, usd);
  }
  for (const o of observaciones) {
    if ((o.fuente === "serpapi" || o.fuente === "fast_flights") && mismaReferencia(o, referencia)) {
      porFecha.set(o.capturado.slice(0, 10), o.precio.monto);
    }
  }
  return [...porFecha].sort(([a], [b]) => a.localeCompare(b)).map(([fecha, usd]) => ({ fecha, usd }));
}

export function serieTravelpayouts(observaciones) {
  return observaciones
    .filter((o) => o.fuente === "travelpayouts")
    .map((o) => ({ fecha: o.capturado.slice(0, 10), usd: o.precio.monto }))
    .sort((a, b) => a.fecha.localeCompare(b.fecha));
}

export function ventana(serie, dias = 90) {
  if (!serie.length) return [];
  const desde = new Date(`${serie.at(-1).fecha}T00:00:00Z`);
  desde.setUTCDate(desde.getUTCDate() - dias);
  const corte = desde.toISOString().slice(0, 10);
  return serie.filter((p) => p.fecha > corte);
}

export function costoTotalClp(viaje, tarifaClp) {
  if (tarifaClp == null) return null;
  return tarifaClp + (viaje.equipaje?.costo_estimado_clp ?? 0) + (viaje.traslados_clp ?? 0);
}

export function mesesDesde(inicio, hasta) {
  const meses = [];
  let [anio, mes] = inicio.split("-").map(Number);
  while (`${anio}-${String(mes).padStart(2, "0")}` <= hasta) {
    meses.push(`${anio}-${String(mes).padStart(2, "0")}`);
    mes === 12 ? ((anio += 1), (mes = 1)) : (mes += 1);
  }
  return meses;
}
