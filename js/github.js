// Cliente mínimo de la API de contenidos de GitHub. El token viaja solo en la cabecera Authorization.

const API = "https://api.github.com";

const MENSAJES = {
  conflicto: "El archivo cambió en GitHub mientras editabas. Vuelve a guardar.",
  token: "Token inválido o vencido. Revísalo en Ajustes.",
  permiso: "El token no tiene acceso de escritura a este repo.",
  red: "No se pudo conectar con GitHub. Revisa tu conexión e inténtalo de nuevo.",
  otro: "GitHub respondió con un error inesperado. Inténtalo de nuevo más tarde.",
};

export class ErrorGithub extends Error {
  constructor(tipo, detalle = "") {
    super(MENSAJES[tipo] + (detalle ? ` (${detalle})` : ""));
    this.tipo = tipo;
    this.mensaje = MENSAJES[tipo];
  }
}

export function aBase64(texto) {
  let binario = "";
  for (const byte of new TextEncoder().encode(texto)) binario += String.fromCharCode(byte);
  return btoa(binario);
}

export function desdeBase64(b64) {
  const binario = atob(b64.replace(/\s/g, ""));
  return new TextDecoder().decode(Uint8Array.from(binario, (c) => c.charCodeAt(0)));
}

export function repoDesdeUbicacion(hostname, pathname, repoAjustes) {
  const pages = hostname.match(/^([a-z0-9-]+)\.github\.io$/i);
  const primerSegmento = pathname.split("/").filter(Boolean)[0];
  if (pages && primerSegmento) return { owner: pages[1], repo: primerSegmento };
  const [owner, repo] = (repoAjustes ?? "").split("/");
  return owner && repo ? { owner, repo } : null;
}

async function pedir({ owner, repo, token }, ruta, opciones, fetchFn) {
  let respuesta;
  try {
    respuesta = await fetchFn(`${API}/repos/${owner}/${repo}${ruta}`, {
      ...opciones,
      headers: {
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        Authorization: `Bearer ${token}`,
        ...(opciones.body ? { "Content-Type": "application/json" } : {}),
      },
    });
  } catch {
    throw new ErrorGithub("red");
  }
  if (respuesta.ok) return respuesta.json();
  const tipo = { 409: "conflicto", 422: "conflicto", 401: "token", 403: "permiso", 404: "permiso" }[respuesta.status] ?? "otro";
  throw new ErrorGithub(tipo, `HTTP ${respuesta.status}`);
}

export async function leerArchivo(cfg, ruta, fetchFn = fetch) {
  const r = await pedir(cfg, `/contents/${ruta}?ref=main`, { method: "GET" }, fetchFn);
  return { datos: JSON.parse(desdeBase64(r.content)), sha: r.sha };
}

export async function escribirArchivo(cfg, ruta, datos, sha, mensaje, fetchFn = fetch) {
  const body = JSON.stringify({ message: mensaje, content: aBase64(JSON.stringify(datos, null, 2) + "\n"), sha, branch: "main" });
  const r = await pedir(cfg, `/contents/${ruta}`, { method: "PUT", body }, fetchFn);
  return r.content.sha;
}

export async function probarToken(cfg, fetchFn = fetch) {
  const r = await pedir(cfg, "", { method: "GET" }, fetchFn);
  return { escritura: r.permissions?.push === true };
}
