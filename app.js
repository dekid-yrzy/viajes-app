const salida = document.getElementById('estado');

try {
  const respuesta = await fetch('data/estado.json', { cache: 'no-store' });
  if (!respuesta.ok) throw new Error(respuesta.status);
  const estado = await respuesta.json();
  salida.textContent = estado.ultima_corrida
    ? 'Última actualización: ' + new Date(estado.ultima_corrida).toLocaleString('es-CL', { timeZone: 'America/Santiago' })
    : 'Aún no hay datos';
} catch {
  salida.textContent = 'No se pudo cargar el estado';
}
