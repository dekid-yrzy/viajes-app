// Percentiles y etiqueta de precio respecto al histórico propio de la ruta.

export const ETIQUETAS = {
  bueno: "Buen precio",
  normal: "Precio normal",
  caro: "Precio alto",
  sin_historia: "Sin historia suficiente",
};

export function percentil(valores, p) {
  if (!valores.length) return null;
  const orden = [...valores].sort((a, b) => a - b);
  const pos = (orden.length - 1) * p;
  const base = Math.floor(pos);
  const resto = pos - base;
  return base + 1 < orden.length ? orden[base] + resto * (orden[base + 1] - orden[base]) : orden[base];
}

// Franja del gráfico: los mismos cuartiles en USD que decide la etiqueta, convertidos con una sola tasa.
export function bandaConvertida(et, convertirUsd) {
  if (et.clave === "sin_historia") return null;
  return { p25: convertirUsd(et.p25), p50: convertirUsd(et.p50), p75: convertirUsd(et.p75) };
}

export function etiqueta(precio, historico, minimo = 14) {
  const p25 = percentil(historico, 0.25);
  const p50 = percentil(historico, 0.5);
  const p75 = percentil(historico, 0.75);
  let clave = "normal";
  if (historico.length < minimo) clave = "sin_historia";
  else if (precio <= p25) clave = "bueno";
  else if (precio >= p75) clave = "caro";
  return { clave, p25, p50, p75 };
}
