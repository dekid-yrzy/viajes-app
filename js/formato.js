// Formato de montos y fechas en es-CL.

const DECIMALES = { CLP: 0, USD: 2, EUR: 2 };

export function moneda(valor, codigo) {
  if (valor == null) return "—";
  const d = DECIMALES[codigo] ?? 2;
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: codigo, minimumFractionDigits: d, maximumFractionDigits: d }).format(valor);
}

export function fechaCorta(iso) {
  return new Intl.DateTimeFormat("es-CL", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" })
    .format(new Date(`${iso.slice(0, 10)}T00:00:00Z`))
    .replace(/\./g, "")
    .replace(/ de /g, " ");
}

export function fechaHora(iso) {
  return new Intl.DateTimeFormat("es-CL", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Santiago" }).format(new Date(iso));
}
