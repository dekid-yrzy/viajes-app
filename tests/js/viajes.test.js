import { test } from "node:test";
import assert from "node:assert/strict";
import { aFormulario, aplicar, cambiarActivo, guardarEnLista, idSugerido, validar, viajesDe } from "../../js/viajes.js";

const HOY = "2026-11-02";
const BASE = aFormulario(null, { origen_defecto: "SCL" });
const ctx = (extra = {}) => ({ existentes: [], original: null, hoy: HOY, ...extra });

test("crea un viaje mes válido con id sugerido y esquema de SPEC 4.3", () => {
  const { viaje, errores } = validar({ ...BASE, destino: "fra", mes: "2027-03", umbral: "950000" }, ctx());
  assert.deepEqual(errores, {});
  assert.equal(viaje.id, "scl-fra-2027-03");
  assert.deepEqual(viaje.fechas, { modo: "mes", mes: "2027-03" });
  assert.deepEqual(viaje.estadia_dias, [14, 21]);
  assert.deepEqual(viaje.equipaje, { facturadas: 1, costo_estimado_clp: 60000 });
  assert.deepEqual([viaje.umbral_clp, viaje.destino, viaje.origen, viaje.tipo, viaje.pasajeros, viaje.activo], [950000, "FRA", "SCL", "ida_vuelta", 1, true]);
  assert.deepEqual(viaje.aeropuertos_alternativos, []);
  assert.equal(viaje.referencia, undefined);
});

test("id repetido recibe sufijo", () => {
  const { viaje } = validar({ ...BASE, destino: "FRA", mes: "2027-03" }, ctx({ existentes: [{ id: "scl-fra-2027-03" }] }));
  assert.equal(viaje.id, "scl-fra-2027-03-2");
  assert.equal(idSugerido("SCL", "FRA", { modo: "fija", salida: "2027-03-10" }, [{ id: "scl-fra-2027-03" }, { id: "scl-fra-2027-03-2" }]), "scl-fra-2027-03-3");
});

test("errores por campo y sin viaje", () => {
  const casos = [
    [{ destino: "FRAN" }, "destino"],
    [{ destino: "SCL" }, "destino"],
    [{ modo: "fija", salida: "2027-03-10", regreso: "2027-03-01" }, "regreso"],
    [{ estadia_min: "21", estadia_max: "14" }, "estadia_min"],
    [{ pasajeros: "0" }, "pasajeros"],
    [{ mes: "2026-09" }, "mes"],
    [{ umbral: "-5" }, "umbral"],
    [{ alternativos: "MUC, cdgx" }, "alternativos"],
    [{ modo: "flexible", salida: "2027-03-10", regreso: "2027-03-28", margen: "30" }, "margen"],
    [{ ref_salida: "2027-04-02", ref_regreso: "2027-04-20" }, "ref_salida"],
  ];
  for (const [cambio, campo] of casos) {
    const r = validar({ ...BASE, destino: "FRA", mes: "2027-03", ...cambio }, ctx());
    assert.equal(r.viaje, null, campo);
    assert.ok(r.errores[campo], `${campo}: ${JSON.stringify(r.errores)}`);
  }
});

test("editar conserva campos desconocidos, el id y permite fechas ya pasadas", () => {
  const original = {
    id: "scl-fra-2026-09", activo: true, origen: "SCL", destino: "FRA", tipo: "ida_vuelta", fechas: { modo: "mes", mes: "2026-09" },
    estadia_dias: [14, 21], pasajeros: 1, equipaje: { facturadas: 1, costo_estimado_clp: 60000 }, traslados_clp: 0, umbral_clp: null,
    permite_self_transfer: true, aeropuertos_alternativos: [], campo_futuro: 7,
  };
  const { viaje, errores } = validar({ ...aFormulario(original, {}), umbral: "800000" }, ctx({ existentes: [original], original }));
  assert.deepEqual(errores, {});
  assert.deepEqual([viaje.id, viaje.pasajeros, viaje.campo_futuro, viaje.umbral_clp], ["scl-fra-2026-09", 1, 7, 800000]);
});

test("referencia opcional dentro de la ventana", () => {
  const { viaje } = validar({ ...BASE, destino: "FRA", mes: "2027-03", ref_salida: "2027-03-09", ref_regreso: "2027-03-26" }, ctx());
  assert.deepEqual(viaje.referencia, { salida: "2027-03-09", regreso: "2027-03-26" });
});

test("flexible y fija arman sus fechas", () => {
  const flex = validar({ ...BASE, destino: "FRA", modo: "flexible", salida: "2027-03-10", regreso: "2027-03-28", margen: "3" }, ctx()).viaje;
  assert.deepEqual(flex.fechas, { modo: "flexible", salida: "2027-03-10", regreso: "2027-03-28", margen_dias: 3 });
  const fija = validar({ ...BASE, destino: "FRA", modo: "fija", salida: "2027-03-10", regreso: "2027-03-28" }, ctx()).viaje;
  assert.deepEqual(fija.fechas, { modo: "fija", salida: "2027-03-10", regreso: "2027-03-28" });
  assert.equal(fija.estadia_dias, undefined);
});

test("solo ida no exige regreso ni estadía", () => {
  const { viaje, errores } = validar({ ...BASE, destino: "MAD", tipo: "ida", modo: "fija", salida: "2027-03-10", regreso: "" }, ctx());
  assert.deepEqual(errores, {});
  assert.deepEqual(viaje.fechas, { modo: "fija", salida: "2027-03-10" });
  assert.equal(viaje.estadia_dias, undefined);
});

test("aFormulario ida y vuelta de un viaje existente", () => {
  const v = validar({ ...BASE, destino: "FRA", mes: "2027-03", alternativos: "muc, cdg" }, ctx()).viaje;
  const f = aFormulario(v, {});
  assert.deepEqual([f.destino, f.mes, f.estadia_min, f.alternativos, f.umbral], ["FRA", "2027-03", "14", "MUC, CDG", ""]);
});

test("aplicar y cambiarActivo no mutan", () => {
  const lista = [{ id: "a", activo: true }];
  assert.deepEqual(aplicar(lista, { id: "b" }, null).map((v) => v.id), ["a", "b"]);
  assert.deepEqual(aplicar(lista, { id: "a", x: 1 }, "a"), [{ id: "a", x: 1 }]);
  assert.equal(cambiarActivo(lista, "a", false)[0].activo, false);
  assert.equal(lista[0].activo, true);
});

const ORIGINAL = validar({ ...BASE, destino: "FRA", mes: "2027-03" }, ctx()).viaje;

test("editar ruta, fechas, tipo o pasajeros crea un viaje nuevo que reemplaza al anterior", () => {
  for (const cambio of [{ destino: "LIS" }, { mes: "2027-05" }, { pasajeros: "2" }, { tipo: "ida" }]) {
    const r = validar({ ...aFormulario(ORIGINAL, {}), ...cambio }, ctx({ existentes: [ORIGINAL], original: ORIGINAL }));
    assert.deepEqual(r.errores, {}, JSON.stringify(cambio));
    assert.notEqual(r.viaje.id, ORIGINAL.id, JSON.stringify(cambio));
    assert.equal(r.reemplaza, ORIGINAL.id);
  }
});

test("editar umbral, equipaje o referencia conserva el id", () => {
  const r = validar({ ...aFormulario(ORIGINAL, {}), umbral: "800000", costo_equipaje: "0", ref_salida: "2027-03-09", ref_regreso: "2027-03-26" }, ctx({ existentes: [ORIGINAL], original: ORIGINAL }));
  assert.equal(r.viaje.id, ORIGINAL.id);
  assert.equal(r.reemplaza, null);
});

test("guardarEnLista: desactiva el reemplazado, agrega el nuevo y evita ids repetidos contra la lista fresca", () => {
  const otro = { id: "scl-lis-2027-03", activo: true };
  const nuevo = { id: "scl-lis-2027-03", activo: true, origen: "SCL", destino: "LIS", fechas: { modo: "mes", mes: "2027-03" } };
  const lista = guardarEnLista([ORIGINAL, otro], nuevo, { reemplaza: ORIGINAL.id });
  assert.deepEqual(lista.map((v) => [v.id, v.activo]), [[ORIGINAL.id, false], ["scl-lis-2027-03", true], ["scl-lis-2027-03-2", true]]);
  const editado = guardarEnLista([ORIGINAL], { ...ORIGINAL, umbral_clp: 1 }, { idOriginal: ORIGINAL.id });
  assert.deepEqual(editado.map((v) => [v.id, v.umbral_clp]), [[ORIGINAL.id, 1]]);
});

test("viajesDe exige una lista; si el archivo remoto no tiene el formato esperado no se escribe", () => {
  assert.deepEqual(viajesDe({ viajes: [] }), []);
  for (const malo of [null, [], {}, { viajes: {} }]) assert.throws(() => viajesDe(malo));
});
