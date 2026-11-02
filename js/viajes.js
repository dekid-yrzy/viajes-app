// Viajes: conversión formulario <-> esquema de config/viajes.json (SPEC 4.3) y validación antes de escribir en el repo.

const IATA = /^[A-Z]{3}$/;
const ENTERO = /^\d+$/;

function fechaValida(s) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s ?? "")) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

function sumarDias(fecha, dias) {
  const d = new Date(`${fecha}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + dias);
  return d.toISOString().slice(0, 10);
}

function entero(s, min, max) {
  const t = String(s ?? "").trim();
  if (!ENTERO.test(t)) return null;
  const n = Number(t);
  return n >= min && n <= max ? n : null;
}

export function aFormulario(viaje, ajustes) {
  if (!viaje) {
    return {
      origen: ajustes?.origen_defecto ?? "SCL", destino: "", tipo: "ida_vuelta", modo: "mes", mes: "", salida: "", regreso: "", margen: "3",
      estadia_min: "14", estadia_max: "21", pasajeros: "1", facturadas: "1", costo_equipaje: "60000", traslados: "0", umbral: "",
      alternativos: "", ref_salida: "", ref_regreso: "", activo: true, permite_self_transfer: true,
    };
  }
  const f = viaje.fechas ?? {};
  return {
    origen: viaje.origen ?? "", destino: viaje.destino ?? "", tipo: viaje.tipo ?? "ida_vuelta", modo: f.modo ?? "mes",
    mes: f.mes ?? "", salida: f.salida ?? "", regreso: f.regreso ?? "", margen: String(f.margen_dias ?? 3),
    estadia_min: String(viaje.estadia_dias?.[0] ?? 14), estadia_max: String(viaje.estadia_dias?.[1] ?? 21),
    pasajeros: String(viaje.pasajeros ?? 1), facturadas: String(viaje.equipaje?.facturadas ?? 0),
    costo_equipaje: String(viaje.equipaje?.costo_estimado_clp ?? 0), traslados: String(viaje.traslados_clp ?? 0),
    umbral: viaje.umbral_clp == null ? "" : String(viaje.umbral_clp),
    alternativos: (viaje.aeropuertos_alternativos ?? []).join(", "),
    ref_salida: viaje.referencia?.salida ?? "", ref_regreso: viaje.referencia?.regreso ?? "",
    activo: viaje.activo !== false, permite_self_transfer: viaje.permite_self_transfer !== false,
  };
}

export function idSugerido(origen, destino, fechas, existentes) {
  const mes = fechas.mes ?? fechas.salida?.slice(0, 7) ?? "";
  const base = `${origen}-${destino}-${mes}`.toLowerCase();
  const usados = new Set(existentes.map((v) => v.id));
  if (!usados.has(base)) return base;
  let n = 2;
  while (usados.has(`${base}-${n}`)) n += 1;
  return `${base}-${n}`;
}

export function validar(v, { existentes, original, hoy }) {
  const e = {};
  const origen = String(v.origen ?? "").trim().toUpperCase();
  const destino = String(v.destino ?? "").trim().toUpperCase();
  if (!IATA.test(origen)) e.origen = "Usa un código IATA de 3 letras (por ejemplo SCL).";
  if (!IATA.test(destino)) e.destino = "Usa un código IATA de 3 letras (por ejemplo FRA).";
  else if (destino === origen) e.destino = "El destino debe ser distinto del origen.";
  const tipo = v.tipo;
  if (!["ida_vuelta", "ida"].includes(tipo)) e.tipo = "Elige ida y vuelta o solo ida.";
  const idaVuelta = tipo === "ida_vuelta";
  const nuevo = !original;

  let fechas = null;
  let ventana = null;
  if (v.modo === "mes") {
    const valido = /^\d{4}-(0[1-9]|1[0-2])$/.test(v.mes ?? "");
    if (!valido) e.mes = "Elige un mes (AAAA-MM).";
    else if (nuevo && v.mes < hoy.slice(0, 7)) e.mes = "El mes ya pasó.";
    else {
      fechas = { modo: "mes", mes: v.mes };
      const [a, m] = v.mes.split("-").map(Number);
      ventana = [`${v.mes}-01`, new Date(Date.UTC(a, m, 0)).toISOString().slice(0, 10)];
    }
  } else if (v.modo === "fija" || v.modo === "flexible") {
    if (!fechaValida(v.salida)) e.salida = "Ingresa la fecha de salida.";
    else if (nuevo && v.salida < hoy) e.salida = "La fecha de salida ya pasó.";
    if (idaVuelta && !fechaValida(v.regreso)) e.regreso = "Ingresa la fecha de regreso.";
    else if (idaVuelta && fechaValida(v.salida) && v.regreso <= v.salida) e.regreso = "El regreso debe ser después de la salida.";
    let margen = 0;
    if (v.modo === "flexible") {
      margen = entero(v.margen, 1, 14);
      if (margen === null) e.margen = "El margen debe ser entre 1 y 14 días.";
    }
    if (!e.salida && !e.regreso && !e.margen) {
      fechas = { modo: v.modo, salida: v.salida, ...(idaVuelta ? { regreso: v.regreso } : {}), ...(v.modo === "flexible" ? { margen_dias: margen } : {}) };
      ventana = [sumarDias(v.salida, -margen), sumarDias(v.salida, margen)];
    }
  } else {
    e.modo = "Elige cómo son las fechas.";
  }

  let estadia;
  if (idaVuelta && v.modo !== "fija") {
    const min = entero(v.estadia_min, 1, 90);
    const max = entero(v.estadia_max, 1, 90);
    if (min === null || max === null) e.estadia_min = "La estadía debe ser entre 1 y 90 días.";
    else if (min > max) e.estadia_min = "El mínimo no puede ser mayor que el máximo.";
    else estadia = [min, max];
  }

  const pasajeros = entero(v.pasajeros, 1, 9);
  if (pasajeros === null) e.pasajeros = "Entre 1 y 9 pasajeros.";
  const facturadas = entero(v.facturadas, 0, 5);
  if (facturadas === null) e.facturadas = "Entre 0 y 5 maletas.";
  const costo = entero(v.costo_equipaje, 0, 1e9);
  if (costo === null) e.costo_equipaje = "Monto en CLP, sin puntos ni decimales.";
  const traslados = entero(v.traslados, 0, 1e9);
  if (traslados === null) e.traslados = "Monto en CLP, sin puntos ni decimales.";
  let umbral = null;
  if (String(v.umbral ?? "").trim() !== "") {
    umbral = entero(v.umbral, 1, 1e10);
    if (umbral === null) e.umbral = "Monto en CLP mayor que 0, o déjalo vacío.";
  }
  const alternativos = String(v.alternativos ?? "").split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
  if (alternativos.some((a) => !IATA.test(a))) e.alternativos = "Códigos IATA de 3 letras separados por coma.";

  let referencia;
  if (v.modo !== "fija" && (v.ref_salida || v.ref_regreso)) {
    if (!fechaValida(v.ref_salida)) e.ref_salida = "Fecha de salida de referencia inválida.";
    else if (ventana && (v.ref_salida < ventana[0] || v.ref_salida > ventana[1])) e.ref_salida = "La salida de referencia debe estar dentro de las fechas del viaje.";
    if (idaVuelta && !fechaValida(v.ref_regreso)) e.ref_regreso = "Fecha de regreso de referencia inválida.";
    else if (idaVuelta && fechaValida(v.ref_salida) && v.ref_regreso <= v.ref_salida) e.ref_regreso = "El regreso debe ser después de la salida.";
    if (!e.ref_salida && !e.ref_regreso) referencia = { salida: v.ref_salida, ...(idaVuelta ? { regreso: v.ref_regreso } : {}) };
  }

  if (Object.keys(e).length) return { viaje: null, errores: e };
  const viaje = {
    id: original ? original.id : idSugerido(origen, destino, fechas, existentes),
    activo: v.activo !== false,
    origen,
    destino,
    aeropuertos_alternativos: alternativos,
    tipo,
    fechas,
    ...(estadia ? { estadia_dias: estadia } : {}),
    pasajeros,
    equipaje: { facturadas, costo_estimado_clp: costo },
    traslados_clp: traslados,
    umbral_clp: umbral,
    permite_self_transfer: v.permite_self_transfer !== false,
    ...(referencia ? { referencia } : {}),
  };
  const resultado = { ...(original ?? {}), ...viaje };
  if (!estadia) delete resultado.estadia_dias;
  if (!referencia) delete resultado.referencia;
  return { viaje: resultado, errores: {} };
}

export function aplicar(lista, viaje, idOriginal) {
  return idOriginal && lista.some((v) => v.id === idOriginal) ? lista.map((v) => (v.id === idOriginal ? viaje : v)) : [...lista, viaje];
}

export function cambiarActivo(lista, id, activo) {
  return lista.map((v) => (v.id === id ? { ...v, activo } : v));
}
