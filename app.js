import { convertir, costoTotalClp, mesesDesde, serieGoogle, serieTravelpayouts, tasaPara, ventana } from "./js/datos.js";
import { ETIQUETAS, bandaConvertida, etiqueta } from "./js/estadistica.js";
import { fechaCorta, fechaHora, moneda as formatoMoneda } from "./js/formato.js";
import { conTooltip, dibujar, geometria } from "./js/grafico.js";
import { ErrorGithub, escribirArchivo, leerArchivo, probarToken, repoDesdeUbicacion } from "./js/github.js";
import { aFormulario, aplicar, cambiarActivo, validar } from "./js/viajes.js";

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
  const agregar = el("a", "boton", "Agregar viaje");
  agregar.href = "#/viaje/nuevo";
  vista.replaceChildren(lista.length ? ul : el("p", "vacio", "No hay viajes activos."), agregar);
}

const TIPOS_ALERTA = { umbral: "Bajo tu umbral", caida_pct: "Caída de precio", minimo_historico: "Mínimo histórico" };
const CANALES = { telegram: "Telegram", email: "Email", app: "App" };

function alertasRecientes(alertas, dias = 7) {
  const desde = Date.now() - dias * 86400000;
  return alertas.filter((a) => Date.parse(a.fecha) >= desde);
}

function renderAlertas(alertas, lista) {
  const rutas = new Map(lista.map((d) => [d.viaje.id, `${d.viaje.origen} → ${d.viaje.destino}`]));
  const partes = [el("h2", "ruta", "Alertas")];
  if (!alertas.length) {
    partes.push(el("p", "vacio", "Todavía no hay alertas."));
    vista.replaceChildren(...partes);
    return;
  }
  const ul = el("ul", "alertas");
  for (const a of [...alertas].reverse()) {
    const li = el("li", "alerta");
    const cabecera = el("div", "alerta-cabecera");
    cabecera.append(el("strong", null, rutas.get(a.viaje_id) ?? a.viaje_id), el("span", "atenuado", fechaHora(a.fecha)));
    li.append(cabecera, el("p", "alerta-tipo", TIPOS_ALERTA[a.tipo] ?? a.tipo), el("p", null, a.motivo ?? ""));
    const pie = el("div", "fila-datos");
    pie.append(el("span", "atenuado", `Costo total estimado: ${formatoMoneda(a.costo_total_clp ?? null, "CLP")}`));
    pie.append(el("span", "atenuado", `Avisado por: ${(a.canales_enviados ?? []).map((c) => CANALES[c] ?? c).join(", ")}`));
    if (rutas.has(a.viaje_id)) {
      const ver = el("a", "secundario", "Ver viaje →");
      ver.href = `#/viaje/${encodeURIComponent(a.viaje_id)}`;
      pie.append(ver);
    }
    li.append(pie);
    ul.append(li);
  }
  partes.push(ul);
  vista.replaceChildren(...partes);
}

function renderDetalle(datos, ctx) {
  const { viaje } = datos;
  const r = resumen(datos, ctx);
  const volver = el("a", "volver", "← Todos los viajes");
  volver.href = "#/";
  const cabecera = el("div", "detalle-cabecera");
  const titulo = el("div");
  const editar = el("a", "secundario enlace-editar", "Editar viaje");
  editar.href = `#/viaje/${encodeURIComponent(viaje.id)}/editar`;
  titulo.append(volver, el("h2", "ruta", `${viaje.origen} → ${viaje.destino}`), el("p", "secundario", textoFechas(viaje, datos.referencia)), editar);
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

// ---- Edición de viajes (H4): token solo en este navegador, escritura vía API de contenidos de GitHub ----

const RUTA_VIAJES = "config/viajes.json";

function leerToken() {
  try {
    return localStorage.getItem("github_token") || null;
  } catch {
    return null;
  }
}

function guardarToken(valor) {
  try {
    if (valor) localStorage.setItem("github_token", valor);
    else localStorage.removeItem("github_token");
    return true;
  } catch {
    return false;
  }
}

function configGithub() {
  const repo = repoDesdeUbicacion(location.hostname, location.pathname, cache.ajustes.repo);
  const token = leerToken();
  return repo && token ? { ...repo, token } : null;
}

function aviso(texto, clase = "aviso") {
  return el("p", clase, texto);
}

async function guardarLista(transformar, mensaje) {
  const cfg = configGithub();
  if (!cfg) throw new ErrorGithub("token");
  const { datos, sha } = await leerArchivo(cfg, RUTA_VIAJES);
  const viajes = transformar(datos.viajes ?? []);
  await escribirArchivo(cfg, RUTA_VIAJES, { ...datos, viajes }, sha, mensaje);
  // Pages tarda en publicar el cambio: la vista usa la lista recién escrita.
  cache.todos = viajes;
  cache.lista = await Promise.all(
    viajes.filter((v) => v.activo).map((v) => {
      const previo = cache.lista.find((d) => d.viaje.id === v.id);
      return previo ? { ...previo, viaje: v } : cargarViaje(v, cache.estado);
    }),
  );
}

function renderAjustes(mensajeLista = "") {
  const partes = [el("h2", "ruta", "Ajustes")];
  const panelToken = el("section", "panel");
  panelToken.append(el("h3", null, "Token de GitHub"));
  const estadoToken = el("p", "secundario", leerToken() ? "Token guardado en este navegador." : "Sin token: puedes ver todo, pero no editar viajes.");
  const mensaje = el("p", "aviso");
  mensaje.setAttribute("role", "status");
  const form = el("form", "formulario-token");
  const etiqueta = el("label", "campo");
  const entrada = el("input");
  Object.assign(entrada, { type: "password", name: "token", autocomplete: "off", spellcheck: false });
  etiqueta.append(el("span", null, "Token (fine-grained)"), entrada);
  const botones = el("div", "botones");
  const guardar = el("button", "boton primario", "Guardar token");
  const probar = el("button", "boton", "Probar");
  const borrar = el("button", "boton", "Borrar token");
  probar.type = borrar.type = "button";
  botones.append(guardar, probar, borrar);
  form.append(etiqueta, botones);
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const valor = entrada.value.trim();
    entrada.value = "";
    if (!valor) return void (mensaje.textContent = "Pega el token antes de guardar.");
    mensaje.textContent = guardarToken(valor) ? "Token guardado en este navegador." : "Este navegador no permite guardar datos (modo privado).";
    estadoToken.textContent = leerToken() ? "Token guardado en este navegador." : "Sin token.";
  });
  probar.addEventListener("click", async () => {
    const cfg = configGithub();
    if (!cfg) return void (mensaje.textContent = "Primero guarda un token.");
    mensaje.textContent = "Probando…";
    try {
      const { escritura } = await probarToken(cfg);
      mensaje.textContent = escritura ? `Puede escribir en ${cfg.owner}/${cfg.repo}.` : "El token puede leer pero no escribir en este repo.";
    } catch (e) {
      mensaje.textContent = e instanceof ErrorGithub ? e.mensaje : "No se pudo probar el token.";
    }
  });
  borrar.addEventListener("click", () => {
    guardarToken(null);
    estadoToken.textContent = "Sin token: puedes ver todo, pero no editar viajes.";
    mensaje.textContent = "Token borrado de este navegador.";
  });
  const ayuda = el("ol", "ayuda");
  const paso1 = el("li");
  const enlace = el("a", null, "Crea un token fine-grained");
  enlace.href = "https://github.com/settings/personal-access-tokens/new";
  enlace.target = "_blank";
  enlace.rel = "noopener noreferrer";
  paso1.append(enlace, document.createTextNode(" con vencimiento (por ejemplo 90 días)."));
  ayuda.append(paso1, el("li", null, "En «Repository access» elige solo el repo viajes-app."), el("li", null, "En «Permissions → Contents» elige «Read and write». Nada más."));
  panelToken.append(estadoToken, form, mensaje, ayuda);

  const panelViajes = el("section", "panel");
  panelViajes.append(el("h3", null, "Viajes"));
  const estadoLista = el("p", "aviso", mensajeLista);
  estadoLista.setAttribute("role", "status");
  const ul = el("ul", "lista-viajes");
  for (const v of cache.todos) {
    const li = el("li");
    const nombre = el("span", null, `${v.origen} → ${v.destino} · ${v.id}${v.activo ? "" : " (inactivo)"}`);
    const editar = el("a", "boton", "Editar");
    editar.href = `#/viaje/${encodeURIComponent(v.id)}/editar`;
    const alternar = el("button", "boton", v.activo ? "Desactivar" : "Reactivar");
    alternar.type = "button";
    alternar.disabled = !configGithub();
    alternar.addEventListener("click", async () => {
      alternar.disabled = true;
      estadoLista.textContent = "Guardando…";
      try {
        await guardarLista((lista) => cambiarActivo(lista, v.id, !v.activo), `Viajes: ${v.activo ? "desactiva" : "reactiva"} ${v.id}`);
        renderAjustes(`Guardado: ${v.id} ${v.activo ? "desactivado" : "reactivado"}.`);
      } catch (e) {
        estadoLista.textContent = e instanceof ErrorGithub ? e.mensaje : "No se pudo guardar.";
        alternar.disabled = false;
      }
    });
    li.append(nombre, editar, alternar);
    ul.append(li);
  }
  const nuevo = el("a", "boton primario", "Agregar viaje");
  nuevo.href = "#/viaje/nuevo";
  panelViajes.append(estadoLista, ul, nuevo);
  partes.push(panelToken, panelViajes);
  vista.replaceChildren(...partes);
}

const CAMPOS = [
  ["Ruta", [
    ["origen", "Origen (IATA)", "text"], ["destino", "Destino (IATA)", "text"],
    ["tipo", "Tipo", [["ida_vuelta", "Ida y vuelta"], ["ida", "Solo ida"]]],
    ["alternativos", "Aeropuertos alternativos (opcional, separados por coma)", "text"],
  ]],
  ["Fechas", [
    ["modo", "Fechas", [["mes", "Mes completo"], ["flexible", "Fecha ± días"], ["fija", "Fechas fijas"]]],
    ["mes", "Mes", "month", { modo: ["mes"] }],
    ["salida", "Salida", "date", { modo: ["fija", "flexible"] }],
    ["regreso", "Regreso", "date", { modo: ["fija", "flexible"], tipo: ["ida_vuelta"] }],
    ["margen", "Margen (± días)", "number", { modo: ["flexible"] }],
    ["estadia_min", "Estadía mínima (días)", "number", { modo: ["mes", "flexible"], tipo: ["ida_vuelta"] }],
    ["estadia_max", "Estadía máxima (días)", "number", { modo: ["mes", "flexible"], tipo: ["ida_vuelta"] }],
    ["ref_salida", "Salida de referencia (opcional)", "date", { modo: ["mes", "flexible"] }],
    ["ref_regreso", "Regreso de referencia (opcional)", "date", { modo: ["mes", "flexible"], tipo: ["ida_vuelta"] }],
  ]],
  ["Pasajeros y equipaje", [
    ["pasajeros", "Pasajeros", "number"], ["facturadas", "Maletas facturadas", "number"],
    ["costo_equipaje", "Costo estimado del equipaje (CLP)", "number"], ["traslados", "Traslados (CLP)", "number"],
  ]],
  ["Alertas", [
    ["umbral", "Umbral de costo total (CLP, opcional)", "number"],
    ["permite_self_transfer", "Permitir combinaciones con self-transfer", "checkbox"],
    ["activo", "Rastrear este viaje", "checkbox"],
  ]],
];

function renderFormulario(original) {
  const titulo = original ? `Editar ${original.origen} → ${original.destino}` : "Agregar viaje";
  const volver = el("a", "volver", "← Ajustes");
  volver.href = "#/ajustes";
  const general = el("p", "aviso");
  general.setAttribute("role", "alert");
  const form = el("form", "formulario");
  form.noValidate = true;
  const valores = aFormulario(original, cache.ajustes);
  const controles = {};
  const filas = {};
  for (const [grupo, campos] of CAMPOS) {
    const fs = el("fieldset");
    fs.append(el("legend", null, grupo));
    for (const [nombre, texto, tipo, condicion] of campos) {
      const fila = el("div", tipo === "checkbox" ? "campo campo-check" : "campo");
      const id = `campo-${nombre}`;
      let control;
      if (Array.isArray(tipo)) {
        control = el("select");
        for (const [valor, etiqueta] of tipo) {
          const op = el("option", null, etiqueta);
          op.value = valor;
          control.append(op);
        }
        control.value = valores[nombre];
      } else {
        control = el("input");
        control.type = tipo;
        if (tipo === "checkbox") control.checked = Boolean(valores[nombre]);
        else control.value = valores[nombre] ?? "";
        if (tipo === "number") Object.assign(control, { inputMode: "numeric", min: "0", step: "1" });
        if (nombre === "origen" || nombre === "destino") Object.assign(control, { maxLength: 3, autocapitalize: "characters" });
      }
      Object.assign(control, { id, name: nombre });
      const label = el("label", null, texto);
      label.htmlFor = id;
      const error = el("p", "error-campo");
      error.id = `${id}-error`;
      fila.append(...(tipo === "checkbox" ? [control, label] : [label, control]), error);
      fs.append(fila);
      controles[nombre] = control;
      filas[nombre] = { fila, condicion, error };
    }
    form.append(fs);
  }
  const visibilidad = () => {
    for (const { fila, condicion } of Object.values(filas)) {
      fila.hidden = Boolean(condicion) && Object.entries(condicion).some(([campo, permitidos]) => !permitidos.includes(controles[campo].value));
    }
  };
  controles.modo.addEventListener("change", visibilidad);
  controles.tipo.addEventListener("change", visibilidad);
  visibilidad();

  const guardar = el("button", "boton primario", "Guardar");
  guardar.type = "submit";
  const cfg = configGithub();
  if (!cfg) {
    guardar.disabled = true;
    const sinToken = el("p", "aviso");
    const ir = el("a", null, "Configura tu token en Ajustes");
    ir.href = "#/ajustes";
    sinToken.append(ir, document.createTextNode(" para poder guardar."));
    form.append(sinToken);
  }
  form.append(guardar);

  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    general.textContent = "";
    const leidos = Object.fromEntries(Object.entries(controles).map(([n, c]) => [n, c.type === "checkbox" ? c.checked : c.value]));
    const { viaje, errores } = validar(leidos, { existentes: cache.todos, original, hoy: new Date().toISOString().slice(0, 10) });
    for (const [nombre, { error }] of Object.entries(filas)) {
      const mensaje = errores[nombre] ?? "";
      error.textContent = mensaje;
      if (mensaje) {
        controles[nombre].setAttribute("aria-invalid", "true");
        controles[nombre].setAttribute("aria-describedby", error.id);
      } else {
        controles[nombre].removeAttribute("aria-invalid");
        controles[nombre].removeAttribute("aria-describedby");
      }
    }
    if (!viaje) {
      const primero = Object.keys(filas).find((n) => errores[n]);
      general.textContent = "Revisa los campos marcados.";
      controles[primero]?.focus();
      return;
    }
    guardar.disabled = true;
    guardar.textContent = "Guardando…";
    try {
      const accion = original ? "edita" : "crea";
      await guardarLista((lista) => aplicar(lista, viaje, original?.id ?? null), `Viajes: ${accion} ${viaje.id}`);
      location.hash = viaje.activo ? `#/viaje/${encodeURIComponent(viaje.id)}` : "#/ajustes";
      setTimeout(() => vista.prepend(aviso("Guardado. El recolector lo tomará en la próxima corrida diaria.")), 0);
    } catch (e) {
      // El formulario no se limpia: lo escrito se conserva para reintentar.
      general.textContent = e instanceof ErrorGithub ? e.mensaje : "No se pudo guardar.";
      guardar.disabled = false;
      guardar.textContent = "Guardar";
    }
  });
  vista.replaceChildren(volver, el("h2", "ruta", titulo), general, form);
}

let cache = null;

async function cargar() {
  const [viajes, ajustes, estado, tasas, alertas] = await Promise.all([
    json("config/viajes.json", { viajes: [] }),
    json("config/ajustes.json", {}),
    json("data/estado.json", {}),
    json("data/tipos_cambio.json", {}),
    json("data/alertas.json", { alertas: [] }),
  ]);
  const recientes = alertasRecientes(alertas?.alertas ?? []).length;
  document.getElementById("enlace-alertas").textContent = recientes ? `Alertas (${recientes})` : "Alertas";
  document.getElementById("actualizado").textContent = estado.ultima_corrida
    ? `Actualizado: ${fechaHora(estado.ultima_corrida)}`
    : "Aún no hay datos";
  const todos = viajes.viajes ?? [];
  const lista = await Promise.all(todos.filter((v) => v.activo).map((v) => cargarViaje(v, estado)));
  return { lista, todos, estado, ajustes, tasas, minimo: ajustes.min_observaciones_percentil ?? 14, alertas: alertas?.alertas ?? [] };
}

async function render() {
  cache ??= await cargar();
  const ctx = { tasas: cache.tasas, minimo: cache.minimo, moneda: selector.value };
  if (location.hash === "#/alertas") {
    document.title = "Alertas · Viajes";
    renderAlertas(cache.alertas, cache.lista);
    return;
  }
  if (location.hash === "#/ajustes") {
    document.title = "Ajustes · Viajes";
    renderAjustes();
    return;
  }
  if (location.hash === "#/viaje/nuevo") {
    document.title = "Agregar viaje · Viajes";
    renderFormulario(null);
    return;
  }
  const edicion = location.hash.match(/^#\/viaje\/(.+)\/editar$/);
  const original = edicion && cache.todos.find((v) => v.id === decodeURIComponent(edicion[1]));
  if (original) {
    document.title = `Editar ${original.origen} → ${original.destino} · Viajes`;
    renderFormulario(original);
    return;
  }
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
