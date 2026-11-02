// Gráfico de líneas en SVG: geometría pura (probada) y dibujo/interacción en el DOM.

const SVG = "http://www.w3.org/2000/svg";
const MARGEN = { arriba: 16, derecha: 56, abajo: 28, izquierda: 72 };
const redondear = (v) => Math.round(v * 10) / 10;
const ms = (fecha) => Date.parse(`${fecha}T00:00:00Z`);

export function escalaLineal([d0, d1], [r0, r1]) {
  if (d0 === d1) return () => (r0 + r1) / 2;
  return (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
}

export function ticksY(min, max, cantidad = 4) {
  if (min === max) [min, max] = [min * 0.9, max * 1.1 || 1];
  const bruto = (max - min) / cantidad;
  const magnitud = 10 ** Math.floor(Math.log10(bruto));
  const norma = bruto / magnitud;
  const paso = (norma <= 1 ? 1 : norma <= 2 ? 2 : norma <= 5 ? 5 : 10) * magnitud;
  const ticks = [];
  for (let v = Math.floor(min / paso) * paso; v <= Math.ceil(max / paso) * paso + paso / 2; v += paso) ticks.push(Math.round(v * 1e6) / 1e6);
  return ticks;
}

export function geometria(series, banda, ancho, alto, margen = MARGEN) {
  const todos = series.flatMap((s) => s.puntos);
  const base = { ancho, alto, margen, ticks: [], rutas: [], puntos: [], banda: null, fechas: [] };
  if (!todos.length) return base;
  const valores = todos.map((p) => p.valor).concat(banda ? [banda.p25, banda.p75] : []);
  const ticks = ticksY(Math.min(...valores) * 0.95, Math.max(...valores) * 1.05);
  const fechas = [...new Set(todos.map((p) => p.fecha))].sort();
  const x = escalaLineal([ms(fechas[0]), ms(fechas.at(-1))], [margen.izquierda, ancho - margen.derecha]);
  const y = escalaLineal([ticks[0], ticks.at(-1)], [alto - margen.abajo, margen.arriba]);
  const puntos = series.flatMap((s) =>
    s.puntos.map((p) => ({ id: s.id, fecha: p.fecha, valor: p.valor, cx: redondear(x(ms(p.fecha))), cy: redondear(y(p.valor)) })),
  );
  const rutas = series
    .filter((s) => s.puntos.length > 1)
    .map((s) => ({
      id: s.id,
      d: puntos.filter((p) => p.id === s.id).map((p, i) => `${i ? "L" : "M"} ${p.cx},${p.cy}`).join(" "),
    }));
  return {
    ...base,
    ticks: ticks.map((v) => ({ valor: v, y: redondear(y(v)) })),
    rutas,
    puntos,
    fechas: fechas.map((f) => ({ fecha: f, x: redondear(x(ms(f))) })),
    banda: banda ? { y25: redondear(y(banda.p25)), y75: redondear(y(banda.p75)), y50: redondear(y(banda.p50)) } : null,
  };
}

function nodo(padre, tag, atributos = {}, texto) {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(atributos)) el.setAttribute(k, v);
  if (texto != null) el.textContent = texto;
  padre.append(el);
  return el;
}

export function dibujar(svg, geo, { formatoY, formatoX, etiquetaUltimo }) {
  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${geo.ancho} ${geo.alto}`);
  const { izquierda, derecha, abajo } = geo.margen;
  for (const t of geo.ticks) {
    nodo(svg, "line", { class: "grilla", x1: izquierda, x2: geo.ancho - derecha, y1: t.y, y2: t.y });
    nodo(svg, "text", { class: "eje", x: izquierda - 8, y: t.y, "text-anchor": "end", "dominant-baseline": "middle" }, formatoY(t.valor));
  }
  if (geo.fechas.length) {
    const [primera, ultima] = [geo.fechas[0], geo.fechas.at(-1)];
    nodo(svg, "text", { class: "eje", x: primera.x, y: geo.alto - abajo + 18, "text-anchor": "start" }, formatoX(primera.fecha));
    if (ultima !== primera) nodo(svg, "text", { class: "eje", x: ultima.x, y: geo.alto - abajo + 18, "text-anchor": "end" }, formatoX(ultima.fecha));
  }
  if (geo.banda) {
    nodo(svg, "rect", { class: "banda", x: izquierda, width: geo.ancho - izquierda - derecha, y: geo.banda.y75, height: Math.max(geo.banda.y25 - geo.banda.y75, 0) });
    nodo(svg, "line", { class: "mediana", x1: izquierda, x2: geo.ancho - derecha, y1: geo.banda.y50, y2: geo.banda.y50 });
  }
  for (const r of geo.rutas) nodo(svg, "path", { class: `linea serie-${r.id}`, d: r.d });
  for (const p of geo.puntos) nodo(svg, "circle", { class: `punto serie-${p.id}`, cx: p.cx, cy: p.cy, r: 4 });
  const ultimo = geo.puntos.filter((p) => p.id === geo.puntos[0]?.id).at(-1);
  if (ultimo && etiquetaUltimo) nodo(svg, "text", { class: "etiqueta-directa", x: ultimo.cx + 8, y: ultimo.cy, "dominant-baseline": "middle" }, etiquetaUltimo);
  return nodo(svg, "line", { class: "crosshair", y1: geo.margen.arriba, y2: geo.alto - abajo, x1: 0, x2: 0, visibility: "hidden" });
}

// Crosshair + tooltip: mouse y flechas del teclado; filasPara(fecha) devuelve [{id, nombre, texto}].
export function conTooltip(contenedor, svg, geo, crosshair, tooltip, filasPara) {
  if (!geo.fechas.length) return;
  let indice = geo.fechas.length - 1;
  const mostrar = (i) => {
    indice = Math.max(0, Math.min(i, geo.fechas.length - 1));
    const { fecha, x } = geo.fechas[indice];
    crosshair.setAttribute("x1", x);
    crosshair.setAttribute("x2", x);
    crosshair.setAttribute("visibility", "visible");
    tooltip.replaceChildren();
    const titulo = document.createElement("div");
    titulo.className = "tooltip-fecha";
    titulo.textContent = filasPara(fecha).titulo;
    tooltip.append(titulo);
    for (const fila of filasPara(fecha).filas) {
      const el = document.createElement("div");
      el.className = "tooltip-fila";
      const clave = document.createElement("span");
      clave.className = `clave-linea serie-${fila.id}`;
      const valor = document.createElement("strong");
      valor.textContent = fila.texto;
      el.append(clave, valor, document.createTextNode(` ${fila.nombre}`));
      tooltip.append(el);
    }
    tooltip.hidden = false;
    const escala = svg.getBoundingClientRect().width / geo.ancho;
    const izquierda = x * escala;
    tooltip.style.left = `${Math.min(izquierda + 12, contenedor.clientWidth - tooltip.offsetWidth - 4)}px`;
  };
  const ocultar = () => {
    crosshair.setAttribute("visibility", "hidden");
    tooltip.hidden = true;
  };
  svg.addEventListener("pointermove", (e) => {
    const escala = geo.ancho / svg.getBoundingClientRect().width;
    const x = (e.clientX - svg.getBoundingClientRect().left) * escala;
    let mejor = 0;
    geo.fechas.forEach((f, i) => { if (Math.abs(f.x - x) < Math.abs(geo.fechas[mejor].x - x)) mejor = i; });
    mostrar(mejor);
  });
  svg.addEventListener("pointerleave", ocultar);
  svg.addEventListener("focus", () => mostrar(indice));
  svg.addEventListener("blur", ocultar);
  svg.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      mostrar(indice + (e.key === "ArrowRight" ? 1 : -1));
    } else if (e.key === "Escape") ocultar();
  });
}
