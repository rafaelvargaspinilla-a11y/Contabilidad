const content = document.querySelector('#content');
const worker = new Worker(new URL('./browser-worker.js', import.meta.url));
const pending = new Map();
let serial = 0;

function request(path, payload = null, bytes = null) {
  return new Promise((resolve, reject) => {
    const id = ++serial;
    pending.set(id, {resolve, reject});
    worker.postMessage({id, path, payload, bytes});
  });
}

worker.onmessage = ({data}) => {
  if (data.progress) {
    content.textContent = data.progress;
    return;
  }
  const promise = pending.get(data.id);
  if (!promise) return;
  pending.delete(data.id);
  if (data.error) promise.reject(new Error(data.error));
  else promise.resolve(data.result);
};
worker.onerror = () => {
  for (const promise of pending.values()) promise.reject(new Error('No se pudo iniciar la aplicación. Recarga la página.'));
  pending.clear();
};

try {
  await request('/api/session');
  globalThis.misCuentasBrowser = {
    request,
    async restore(file, mode) {
      if (!file || file.size > 50 * 1024 * 1024) throw new Error('Elige un respaldo SQLite de hasta 50 MB.');
      return request('/api/restore', {mode}, new Uint8Array(await file.arrayBuffer()));
    },
  };
  document.title = 'Mis cuentas';
  document.querySelector('.sidebar-bottom').innerHTML = '<span class="status-dot"></span> Guardado en este dispositivo<small>Academia · Baile · Personal</small>';
  document.querySelector('footer').textContent = 'Mis cuentas · Datos locales en este navegador · Sin sincronización entre dispositivos';
  const notice = document.createElement('div');
  notice.className = 'device-notice';
  notice.textContent = 'Tus cuentas se guardan en este navegador. Descarga respaldos para conservarlas o trasladarlas a otro dispositivo.';
  document.querySelector('.topbar').after(notice);
  await import('./app.js');
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register(new URL('./sw.js', import.meta.url))
      .then(() => navigator.serviceWorker.ready)
      .then(() => { document.querySelector('footer').textContent += ' · Disponible sin conexión'; })
      .catch(() => {
        notice.textContent += ' No se pudo preparar el uso sin conexión; mantén Internet disponible.';
      });
  }
} catch (error) {
  content.textContent = `${error.message} Comprueba la conexión y vuelve a cargar. Tus datos guardados no se han borrado.`;
}
