import {SupabaseAuth} from './supabase-auth.mjs';

const content = document.querySelector('#content');
const worker = new Worker(new URL('./browser-worker.js', import.meta.url));
const pending = new Map();
let serial = 0;
let cloudConfig;
let auth;

async function request(path, payload = null, bytes = null) {
  const cloud = auth ? {...cloudConfig, session: await auth.ensureSession()} : null;
  return new Promise((resolve, reject) => {
    const id = ++serial;
    pending.set(id, {resolve, reject});
    worker.postMessage({id, path, payload, bytes, cloud});
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
  if (data.error) {
    globalThis.dispatchEvent(new CustomEvent('miscuentas-warning', {detail: data.error}));
    promise.reject(new Error(data.error));
  }
  else {
    if (data.result?.__sync && globalThis.misCuentasBrowser) {
      globalThis.misCuentasBrowser.sync = data.result.__sync;
      globalThis.dispatchEvent(new CustomEvent('miscuentas-sync', {detail: data.result.__sync}));
    }
    promise.resolve(data.result);
  }
};
worker.onerror = () => {
  for (const promise of pending.values()) promise.reject(new Error('No se pudo iniciar la aplicación. Recarga la página.'));
  pending.clear();
};

try {
  const response = await fetch(new URL('./cloud-config.json', import.meta.url), {cache: 'no-store'});
  if (!response.ok) throw new Error('No se pudo cargar la configuración de la aplicación.');
  cloudConfig = await response.json();
  if (cloudConfig.enabled) {
    auth = new SupabaseAuth(cloudConfig);
    await auth.acquire();
    auth.onSignOut = () => { worker.terminate(); location.reload(); };
  }
  await request('/api/session');
  globalThis.misCuentasBrowser = {
    request,
    cloud: Boolean(auth),
    accountId: auth?.session.user.id,
    sync: {offline: false, updatedAt: null},
    async restore(file, mode) {
      if (!file || file.size > 50 * 1024 * 1024) throw new Error('Elige un respaldo SQLite de hasta 50 MB.');
      return request('/api/restore', {mode}, new Uint8Array(await file.arrayBuffer()));
    },
  };
  document.title = 'Mis cuentas';
  document.querySelector('.sidebar-bottom').innerHTML = `<span class="status-dot"></span> ${auth ? 'Cuenta privada en Supabase' : 'Guardado en este dispositivo'}<small>Academia · Baile · Personal</small>`;
  document.querySelector('footer').textContent = auth ? 'Mis cuentas · Datos compartidos con tu cuenta de Supabase' : 'Mis cuentas · Modo local · Sin sincronización entre dispositivos';
  const notice = document.createElement('div');
  notice.className = 'device-notice';
  notice.textContent = auth ? 'Conectando con tus cuentas…' : 'Modo local: tus cuentas se guardan solo en este navegador. Supabase todavía no está configurado.';
  document.querySelector('.topbar').after(notice);
  if (auth) {
    const logout = document.createElement('button');
    logout.className = 'button'; logout.textContent = 'Cerrar sesión'; logout.id = 'cloud-logout';
    logout.onclick = async () => {
      logout.disabled = true;
      document.querySelector('.shell').hidden = true;
      document.querySelector('.sidebar').hidden = true;
      try { await request('/api/logout'); } finally {
        worker.terminate(); await auth.logout(); location.reload();
      }
    };
    document.querySelector('.top-controls').append(logout);
    const refresh = document.createElement('button');
    refresh.className = 'button'; refresh.textContent = 'Actualizar'; refresh.dataset.action = 'refresh';
    document.querySelector('.top-controls').append(refresh);
    globalThis.addEventListener('miscuentas-sync', ({detail}) => {
      notice.textContent = detail.offline ? `Sin conexión · Solo consulta${detail.updatedAt ? ' · Última actualización: ' + new Date(detail.updatedAt).toLocaleString('es-ES') : ''}. No se guardan cambios.` : 'Tus cuentas están compartidas entre dispositivos. Pulsa Actualizar para consultar los últimos cambios.';
    });
    globalThis.addEventListener('miscuentas-warning', ({detail}) => { notice.textContent = detail; });
  }
  await import('./app.js');
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register(new URL('./sw.js', import.meta.url))
      .then(() => navigator.serviceWorker.ready)
      .then(() => { document.querySelector('footer').textContent += auth ? ' · Consulta sin conexión' : ' · Disponible sin conexión'; })
      .catch(() => {
        notice.textContent += ' No se pudo preparar el uso sin conexión; mantén Internet disponible.';
      });
  }
} catch (error) {
  content.textContent = `${error.message} Comprueba la conexión y vuelve a cargar. Tus datos guardados no se han borrado.`;
}
