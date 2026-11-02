import { test } from "node:test";
import assert from "node:assert/strict";
import { ErrorGithub, aBase64, desdeBase64, escribirArchivo, leerArchivo, probarToken, repoDesdeUbicacion } from "../../js/github.js";

const CFG = { owner: "dekid-yrzy", repo: "viajes-app", token: "TOKEN-SECRETO" };

function falso(respuestas) {
  const f = async (url, opciones) => {
    f.llamadas.push({ url, opciones });
    const r = respuestas.shift();
    return { ok: r.status >= 200 && r.status < 300, status: r.status, json: async () => r.body };
  };
  f.llamadas = [];
  return f;
}

test("base64 UTF-8 ida y vuelta, con saltos de línea", () => {
  const texto = '{"ruta": "SCL → FRA", "nota": "Múnich, ñandú"}\n';
  const b64 = aBase64(texto);
  assert.equal(desdeBase64(b64.replace(/(.{20})/g, "$1\n")), texto);
});

test("repo desde la URL de Pages o de ajustes", () => {
  assert.deepEqual(repoDesdeUbicacion("dekid-yrzy.github.io", "/viajes-app/"), { owner: "dekid-yrzy", repo: "viajes-app" });
  assert.deepEqual(repoDesdeUbicacion("localhost", "/", "dekid-yrzy/viajes-app"), { owner: "dekid-yrzy", repo: "viajes-app" });
  assert.equal(repoDesdeUbicacion("localhost", "/"), null);
});

test("leerArchivo decodifica y devuelve el sha; el token va solo en la cabecera", async () => {
  const f = falso([{ status: 200, body: { content: aBase64('{"viajes":[]}\n'), sha: "abc" } }]);
  const r = await leerArchivo(CFG, "config/viajes.json", f);
  assert.deepEqual(r, { datos: { viajes: [] }, sha: "abc" });
  assert.equal(f.llamadas[0].url, "https://api.github.com/repos/dekid-yrzy/viajes-app/contents/config/viajes.json?ref=main");
  assert.equal(f.llamadas[0].opciones.headers.Authorization, "Bearer TOKEN-SECRETO");
  assert.ok(!f.llamadas[0].url.includes("TOKEN"));
});

test("escribirArchivo hace PUT con sha, rama y contenido formateado", async () => {
  const f = falso([{ status: 200, body: { content: { sha: "nuevo" } } }]);
  const sha = await escribirArchivo(CFG, "config/viajes.json", { viajes: [] }, "abc", "Viajes: crea x", f);
  const cuerpo = JSON.parse(f.llamadas[0].opciones.body);
  assert.equal(sha, "nuevo");
  assert.equal(f.llamadas[0].opciones.method, "PUT");
  assert.deepEqual([cuerpo.sha, cuerpo.branch, cuerpo.message], ["abc", "main", "Viajes: crea x"]);
  assert.equal(desdeBase64(cuerpo.content), '{\n  "viajes": []\n}\n');
});

test("errores tipados en español sin el token", async () => {
  for (const [status, tipo] of [[409, "conflicto"], [422, "conflicto"], [401, "token"], [403, "permiso"], [404, "permiso"], [500, "otro"]]) {
    const e = await escribirArchivo(CFG, "config/viajes.json", {}, "abc", "m", falso([{ status, body: { message: "x" } }])).catch((x) => x);
    assert.ok(e instanceof ErrorGithub);
    assert.equal(e.tipo, tipo);
    assert.ok(!e.message.includes("TOKEN-SECRETO"));
  }
  const red = await leerArchivo(CFG, "config/viajes.json", async () => {
    throw new TypeError("Failed to fetch");
  }).catch((x) => x);
  assert.equal(red.tipo, "red");
});

test("probarToken informa permiso de escritura", async () => {
  assert.deepEqual(await probarToken(CFG, falso([{ status: 200, body: { permissions: { push: true } } }])), { escritura: true });
  assert.deepEqual(await probarToken(CFG, falso([{ status: 200, body: { permissions: { push: false } } }])), { escritura: false });
});
