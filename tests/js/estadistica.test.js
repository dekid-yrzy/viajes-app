import { test } from "node:test";
import assert from "node:assert/strict";
import { bandaConvertida, etiqueta, percentil } from "../../js/estadistica.js";

test("percentil interpola linealmente", () => {
  const v = [40, 10, 30, 20];
  assert.equal(percentil(v, 0.25), 17.5);
  assert.equal(percentil(v, 0.5), 25);
  assert.equal(percentil(v, 0.75), 32.5);
  assert.deepEqual(v, [40, 10, 30, 20]);
  assert.equal(percentil([], 0.5), null);
  assert.equal(percentil([7], 0.9), 7);
});

test("etiqueta según cuartiles con mínimo de observaciones", () => {
  const hist = Array.from({ length: 20 }, (_, i) => 100 + i * 10); // 100..290
  assert.equal(etiqueta(140, hist).clave, "bueno"); // p25 = 147.5
  assert.equal(etiqueta(200, hist).clave, "normal");
  assert.equal(etiqueta(260, hist).clave, "caro"); // p75 = 242.5
  assert.equal(etiqueta(140, hist.slice(0, 13)).clave, "sin_historia");
  assert.equal(etiqueta(140, hist).p50, 195);
});

test("bandaConvertida usa los mismos cuartiles que la etiqueta, convertidos con una sola tasa", () => {
  const hist = Array.from({ length: 20 }, (_, i) => 100 + i * 10);
  const et = etiqueta(140, hist);
  assert.deepEqual(bandaConvertida(et, (usd) => usd * 1000), { p25: 147500, p50: 195000, p75: 242500 });
  assert.equal(bandaConvertida(etiqueta(140, hist.slice(0, 5)), (usd) => usd), null);
});
