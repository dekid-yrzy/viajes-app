import { test } from "node:test";
import assert from "node:assert/strict";
import { convertir, costoTotalClp, mesesDesde, serieGoogle, serieTravelpayouts, tasaPara, ventana } from "../../js/datos.js";
import { fechaCorta, moneda } from "../../js/formato.js";

const TASAS = { "2026-11-02": { USD: 990.8, EUR: 1150.0 }, "2026-11-03": { USD: 1000, EUR: 1160 } };

test("tasaPara usa la más reciente anterior y, si no hay, la más antigua", () => {
  assert.deepEqual(tasaPara(TASAS, "2026-11-05"), { USD: 1000, EUR: 1160 });
  assert.deepEqual(tasaPara(TASAS, "2026-11-02"), { USD: 990.8, EUR: 1150.0 });
  assert.deepEqual(tasaPara(TASAS, "2026-09-03"), { USD: 990.8, EUR: 1150.0 });
  assert.equal(tasaPara({}, "2026-11-02"), null);
});

test("convertir", () => {
  const t = { USD: 1000, EUR: 1160 };
  assert.equal(convertir(966, "CLP", t), 966000);
  assert.equal(convertir(966, "EUR", t), 832.76);
  assert.equal(convertir(966, "USD", null), 966);
  assert.equal(convertir(966, "CLP", null), null);
});

test("serieGoogle une historial y observaciones de la referencia vigente", () => {
  const ref = { salida: "2027-03-01", regreso: "2027-03-18" };
  const hist = { ...ref, puntos: [["2026-11-01", 950], ["2026-11-02", 960]] };
  const obs = [
    { fuente: "serpapi", capturado: "2026-11-02T11:00:00Z", salida: "2027-03-01", regreso: "2027-03-18", precio: { monto: 966 } },
    { fuente: "fast_flights", capturado: "2026-11-03T11:00:00Z", salida: "2027-03-01", regreso: "2027-03-18", precio: { monto: 970 } },
    { fuente: "serpapi", capturado: "2026-11-04T11:00:00Z", salida: "2027-03-09", regreso: "2027-03-26", precio: { monto: 1 } },
    { fuente: "travelpayouts", capturado: "2026-11-04T11:00:00Z", salida: "2027-03-01", regreso: "2027-03-18", precio: { monto: 2 } },
  ];
  assert.deepEqual(serieGoogle(hist, obs, ref), [
    { fecha: "2026-11-01", usd: 950 },
    { fecha: "2026-11-02", usd: 966 },
    { fecha: "2026-11-03", usd: 970 },
  ]);
  assert.deepEqual(serieGoogle({ salida: "2027-02-01", regreso: "2027-02-10", puntos: [["2026-11-01", 1]] }, [], ref), []);
  assert.deepEqual(serieGoogle(null, [], null), []);
  assert.deepEqual(serieTravelpayouts(obs), [{ fecha: "2026-11-04", usd: 2 }]);
});

test("ventana, costo total y meses", () => {
  const serie = [{ fecha: "2026-07-01", usd: 1 }, { fecha: "2026-10-01", usd: 2 }, { fecha: "2026-11-02", usd: 3 }];
  assert.deepEqual(ventana(serie, 90).map((p) => p.usd), [2, 3]);
  assert.deepEqual(ventana([], 90), []);
  assert.equal(costoTotalClp({ equipaje: { costo_estimado_clp: 60000 }, traslados_clp: 0 }, 957151), 1017151);
  assert.equal(costoTotalClp({}, null), null);
  assert.deepEqual(mesesDesde("2026-11", "2027-02"), ["2026-11", "2026-12", "2027-01", "2027-02"]);
});

test("formato", () => {
  assert.equal(moneda(null, "CLP"), "—");
  assert.match(moneda(957151, "CLP"), /957\.151/);
  assert.equal(fechaCorta("2027-03-08"), "8 mar 2027");
});
