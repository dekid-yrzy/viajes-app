import { test } from "node:test";
import assert from "node:assert/strict";
import { escalaLineal, geometria, ticksY } from "../../js/grafico.js";

test("escalaLineal", () => {
  const e = escalaLineal([0, 10], [100, 200]);
  assert.equal(e(5), 150);
  assert.equal(escalaLineal([3, 3], [0, 10])(3), 5);
});

test("ticksY redondos", () => {
  assert.deepEqual(ticksY(840, 1350), [800, 1000, 1200, 1400]);
  assert.deepEqual(ticksY(950, 950).length > 0, true);
});

test("geometria arma rutas y puntos dentro del área", () => {
  const geo = geometria(
    [
      { id: "google", puntos: [{ fecha: "2026-11-01", valor: 900 }, { fecha: "2026-11-03", valor: 1000 }] },
      { id: "tp", puntos: [{ fecha: "2026-11-02", valor: 950 }] },
    ],
    { p25: 900, p50: 950, p75: 1000 },
    400,
    200,
  );
  assert.equal(geo.rutas.length, 1);
  assert.match(geo.rutas[0].d, /^M 72,\d+(\.\d)? L 344,\d+(\.\d)?$/);
  assert.equal(geo.puntos.length, 3);
  for (const p of geo.puntos) {
    assert.ok(p.cx >= 72 && p.cx <= 344);
    assert.ok(p.cy >= 16 && p.cy <= 172);
  }
  assert.ok(geo.banda.y75 < geo.banda.y25);
});

test("geometria sin datos no rompe", () => {
  const geo = geometria([{ id: "google", puntos: [] }], null, 400, 200);
  assert.deepEqual([geo.rutas, geo.puntos, geo.banda], [[], [], null]);
});
