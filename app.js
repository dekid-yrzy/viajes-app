import { convertir, costoTotalClp, mesesDesde, serieGoogle, serieTravelpayouts, tasaPara, ventana } from "./js/datos.js";
import { ETIQUETAS, bandaConvertida, etiqueta } from "./js/estadistica.js";
import { fechaCorta, fechaHora, moneda as formatoMoneda } from "./js/formato.js";
import { conTooltip, dibujar, geometria } from "./js/grafico.js";

const vista = document.getElementById("vista");
const selector = document.getElementById("moneda");
const NIVELES = { low: "bajo", typical: "típico", high: "alto" };
const ICONOS = { bueno: "✓", caro: "▲", normal: "•", sin_historia: "○" };
const NOMBRES = { google: "Google Flights", tp: "Travelpayouts (caché)" };

function leerMoneda() {
  try {
    const guardada = localStorage.getItem("moneda");
    return ["CLP", "USD", "EUR"].includes(guardada) ? guardada : "CLP";
  } catch {
    return "CLP";
  }
}

function guardarMoneda(valor) {
  try {
    localStorage.setItem("moneda", valor);
  } catch {
    // sin almacenamiento: la elección dura solo esta visita
  }
}

async function json(ruta, defecto) {
  try {
    const r = await fetch(ruta, { cache: "no-store" });
    return r.ok ? await r.json() : defecto;
  } catch {
    return defecto;
  }
}

function el(tag, clase, texto) {
  const e = document.createElement(tag);
  if (clase) e.className = clase;
  if (texto != null) e.textContent = texto;
  return e;
}

// shortcut: recorre meses desde 2026-11; con más de 24 meses conviene un índice generado por el recolector
async function cargarViaje(viaje, estado) {
  const hasta = new Date().toISOString().slice(0, 7);
  const [historial, ...meses] = await Promise.all([
    json(`data/historial_google/${viaje.id}.json`, null),
    ...mesesDesde("2026-11", hasta).map((m) => json(`data/precios/${viaje.id}/${m}.json`, null)),
  ]);
  const observaciones = meses.flatMap((m) => m?.observaciones ?? []);
  const referencia =
    estado.viajes?.[viaje.id]?.referencia ??
    viaje.referencia ??
    (viaje.fechas.modo === "fija" ? { salida: viaje.fechas.salida, regreso: viaje.fechas.regreso ?? null } : null);
  const google = serieGoogle(historial, observaciones, referencia);
  const enVivo = observaciones.filter((o) => o.fuente === "serpapi" || o.fuente === "fast_flights").at(-1) ?? null;
  const ultimaSerpapi = observaciones.filter((o) => o.fuente === "serpapi").at(-1) ?? null;
  return { viaje, referencia, google, tp: serieTravelpayouts(observaciones), enVivo, ultimaSerpapi };
}

function resumen(datos, ctx) {
  const ultimo = datos.google.at(-1) ?? null;
  const historico = ventana(datos.google, 90).map((p) => p.usd);
  const et = ultimo ? etiqueta(ultimo.usd, historico, ctx.minimo) : null;
  const tasaHoy = ultimo ? tasaPara(ctx.tasas, ultimo.fecha) : null;
  const tarifaClp = ultimo ? convertir(ultimo.usd, "CLP", tasaHoy) : null;
  return { ultimo, et, tasaHoy, tarifaClp, total: costoTotalClp(datos.viaje, tarifaClp) };
}

function chip(clave) {
  const c = el("span", `chip chip-${clave}`);
  c.append(el("span", "chip-icono", ICONOS[clave]), el("span", null, ETIQUETAS[clave]));
  c.querySelector(".chip-icono").setAttribute("aria-hidden", "true");
  return c;
}

function textoFechas(viaje, referencia) {
  if (!referencia) return "Fechas de referencia pendientes";
  const partes = [fechaCorta(referencia.salida)];
  if (referencia.regreso) {
    const dias = Math.round((Date.parse(referencia.regreso) - Date.parse(referencia.salida)) / 86400000);
    partes.push(`→ ${fechaCorta(referencia.regreso)} · ${dias} días`);
  }
  partes.push(`· ${viaje.pasajeros} ${viaje.pasajeros === 1 ? "pasajero" : "pasajeros"}`);
  return partes.join(" ");
}

function precioEn(usd, fecha, ctx) {
  return formatoMoneda(convertir(usd, ctx.moneda, tasaPara(ctx.tasas, fecha)), ctx.moneda);
}

function renderInicio(lista, ctx) {
  const ul = el("ul", "tarjetas");
  for (const datos of lista) {
    const { viaje } = datos;
    const r = resumen(datos, ctx);
    const a = el("a", "tarjeta");
    a.href = `#/viaje/${encodeURIComponent(viaje.id)}`;
    a.append(el("p", "ruta", `${viaje.origen} → ${viaje.destino}`), el("p", "secundario", textoFechas(viaje, datos.referencia)));
    if (!r.ultimo) {
      a.append(el("p", "precio vacio", "Aún sin precios"));
    } else {
      a.append(el("p", "precio", precioEn(r.ultimo.usd, r.ultimo.fecha, ctx)), chip(r.et.clave));
      const fila = el("div", "fila-datos");
      if (datos.enVivo?.nivel) fila.append(el("span", "atenuado", `Google: ${NIVELES[datos.enVivo.nivel] ?? datos.enVivo.nivel}`));
      fila.append(el("span", "atenuado", `Costo total estimado: ${formatoMoneda(r.total, "CLP")}`));
      a.append(fila);
    }
    const li = el("li");
    li.append(a);
    ul.append(li);
  }
  vista.replaceChildren(lista.length ? ul : el("p", "vacio", "No hay viajes activos."));
}

function renderDetalle(datos, ctx) {
  const { viaje } = datos;
  const r = resumen(datos, ctx);
  const volver = el("a", "volver", "← Todos los viajes");
  volver.href = "#/";
  const cabecera = el("div", "detalle-cabecera");
  const titulo = el("div");
  titulo.append(volver, el("h2", "ruta", `${viaje.origen} → ${viaje.destino}`), el("p", "secundario", textoFechas(viaje, datos.referencia)));
  cabecera.append(titulo);
  const partes = [cabecera];

  if (!r.ultimo) {
    partes.push(el("p", "vacio", "Aún sin precios para este viaje. Aparecerán después de la próxima recolección diaria."));
    vista.replaceChildren(...partes);
    return;
  }

  const precio = el("div");
  precio.append(el("p", "precio precio-grande", precioEn(r.ultimo.usd, r.ultimo.fecha, ctx)), chip(r.et.clave));
  const rango = datos.ultimaSerpapi?.rango_tipico;
  if (rango) precio.append(el("p", "atenuado", `Rango típico según Google: ${precioEn(rango[0], r.ultimo.fecha, ctx)} – ${precioEn(rango[1], r.ultimo.fecha, ctx)}`));
  const desglose = el("dl", "desglose");
  const filas = [
    ["Pasaje", r.tarifaClp],
    ["Equipaje", viaje.equipaje?.costo_estimado_clp ?? 0],
    ["Traslados", viaje.traslados_clp ?? 0],
  ];
  for (const [nombre, valor] of filas) desglose.append(el("dt", null, nombre), el("dd", null, formatoMoneda(valor, "CLP")));
  desglose.append(el("dt", "total", "Costo total estimado"), el("dd", "total", formatoMoneda(r.total, "CLP")));
  cabecera.append(precio, desglose);

  partes.push(panelGrafico(datos, r, ctx));
  if (datos.ultimaSerpapi?.enlace) {
    const enlace = el("a", "secundario", "Ver en Google Flights ↗");
    enlace.href = datos.ultimaSerpapi.enlace;
    enlace.rel = "noopener noreferrer";
    enlace.target = "_blank";
    partes.push(enlace);
  }
  vista.replaceChildren(...partes);
}

function panelGrafico(datos, r, ctx) {
  const panel = el("section", "panel");
  panel.setAttribute("aria-label", "Histórico de precios");
  const valor = (p) => convertir(p.usd, ctx.moneda, tasaPara(ctx.tasas, p.fecha));
  const series = [
    { id: "google", puntos: datos.google.map((p) => ({ fecha: p.fecha, valor: valor(p) })).filter((p) => p.valor != null) },
    { id: "tp", puntos: datos.tp.map((p) => ({ fecha: p.fecha, valor: valor(p) })).filter((p) => p.valor != null) },
  ];
  const banda = bandaConvertida(r.et, (usd) => convertir(usd, ctx.moneda, r.tasaHoy));

  const leyenda = el("ul", "leyenda");
  for (const s of series.filter((s) => s.puntos.length)) {
    const li = el("li");
    li.append(el("span", `clave-linea serie-${s.id}`), document.createTextNode(NOMBRES[s.id]));
    leyenda.append(li);
  }
  if (banda) {
    const li = el("li");
    li.append(document.createTextNode("Franja: rango normal (p25–p75, 90 días)"));
    leyenda.append(li);
  }

  const contenedor = el("div", "grafico");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("tabindex", "0");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Gráfico del precio por fecha de consulta. Usa las flechas para recorrerlo; la tabla tiene los mismos datos.");
  const tooltip = el("div", "tooltip");
  tooltip.hidden = true;
  contenedor.append(svg, tooltip);
  // shortcut: el ancho se fija al pintar (panel = vista − 34 px de padding y borde); no se recalcula al rotar la pantalla
  const ancho = Math.max(300, Math.min(720, vista.clientWidth - 34));
  const geo = geometria(series, banda, ancho, ancho < 480 ? 240 : 300);
  const ultimoGoogle = series[0].puntos.at(-1);
  const crosshair = dibujar(svg, geo, {
    formatoY: (v) => formatoMoneda(v, ctx.moneda).replace(/[,.]00$/, ""),
    formatoX: fechaCorta,
    etiquetaUltimo: ultimoGoogle ? formatoMoneda(ultimoGoogle.valor, ctx.moneda) : null,
  });
  const porFecha = (serie) => new Map(serie.puntos.map((p) => [p.fecha, p.valor]));
  const mapas = series.map((s) => [s.id, porFecha(s)]);
  conTooltip(contenedor, svg, geo, crosshair, tooltip, (fecha) => ({
    titulo: fechaCorta(fecha),
    filas: mapas.filter(([, m]) => m.has(fecha)).map(([id, m]) => ({ id, nombre: NOMBRES[id], texto: formatoMoneda(m.get(fecha), ctx.moneda) })),
  }));

  const detalles = el("details");
  detalles.append(el("summary", null, "Ver tabla"));
  const tabla = el("table");
  const cab = el("tr");
  for (const t of ["Fecha", NOMBRES.google, NOMBRES.tp]) cab.append(el("th", null, t));
  const thead = el("thead");
  thead.append(cab);
  const tbody = el("tbody");
  const fechas = [...new Set(series.flatMap((s) => s.puntos.map((p) => p.fecha)))].sort().reverse();
  for (const f of fechas) {
    const tr = el("tr");
    tr.append(el("td", null, fechaCorta(f)));
    for (const [, m] of mapas) tr.append(el("td", null, m.has(f) ? formatoMoneda(m.get(f), ctx.moneda) : "—"));
    tbody.append(tr);
  }
  tabla.append(thead, tbody);
  const scroll = el("div", "tabla-contenedor");
  scroll.append(tabla);
  detalles.append(scroll);

  panel.append(leyenda, contenedor, detalles);
  return panel;
}

let cache = null;

async function cargar() {
  const [viajes, ajustes, estado, tasas] = await Promise.all([
    json("config/viajes.json", { viajes: [] }),
    json("config/ajustes.json", {}),
    json("data/estado.json", {}),
    json("data/tipos_cambio.json", {}),
  ]);
  document.getElementById("actualizado").textContent = estado.ultima_corrida
    ? `Actualizado: ${fechaHora(estado.ultima_corrida)}`
    : "Aún no hay datos";
  const activos = (viajes.viajes ?? []).filter((v) => v.activo);
  const lista = await Promise.all(activos.map((v) => cargarViaje(v, estado)));
  return { lista, tasas, minimo: ajustes.min_observaciones_percentil ?? 14 };
}

async function render() {
  cache ??= await cargar();
  const ctx = { tasas: cache.tasas, minimo: cache.minimo, moneda: selector.value };
  const ruta = location.hash.match(/^#\/viaje\/(.+)$/);
  if (ruta) {
    const datos = cache.lista.find((d) => d.viaje.id === decodeURIComponent(ruta[1]));
    if (datos) {
      renderDetalle(datos, ctx);
      document.title = `${datos.viaje.origen} → ${datos.viaje.destino} · Viajes`;
      return;
    }
  }
  document.title = "Viajes";
  renderInicio(cache.lista, ctx);
}

selector.value = leerMoneda();
selector.addEventListener("change", () => {
  guardarMoneda(selector.value);
  render();
});
window.addEventListener("hashchange", () => {
  render();
  window.scrollTo(0, 0);
});
vista.replaceChildren(el("p", "vacio", "Cargando viajes…"));
render().catch(() => vista.replaceChildren(el("p", "vacio", "No se pudieron cargar los datos.")));
