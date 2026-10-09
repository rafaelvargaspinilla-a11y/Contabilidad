/* Motor contable local; el modo nube guarda registros privados en Supabase. */
importScripts('./runtime/pyodide.js');
importScripts('./supabase-rest.js');

let dbName = 'mis-cuentas:' + new URL('.', self.location.href).pathname;
let database;
let python;
let initialization;
let queue = Promise.resolve();
let cloud;
let repository;
let viewRevision = null;
let sync = {offline: false, updatedAt: null};

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(dbName, 1);
    request.onupgradeneeded = () => request.result.createObjectStore('files');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('No se puede guardar en este navegador. Desactiva el modo privado o revisa sus permisos.'));
  });
}

function readFile(key) {
  return new Promise((resolve, reject) => {
    const tx = database.transaction('files', 'readonly');
    const request = tx.objectStore('files').get(key);
    tx.oncomplete = () => resolve(request.result);
    tx.onabort = () => reject(new Error('No se pudo leer la copia local.'));
  });
}

function writeFiles(entries) {
  return new Promise((resolve, reject) => {
    const tx = database.transaction('files', 'readwrite');
    for (const [key, value] of entries) tx.objectStore('files').put(value, key);
    tx.oncomplete = resolve;
    tx.onabort = () => reject(new Error('No se han guardado los cambios. El navegador no permite escribir o se ha quedado sin espacio. Descarga un respaldo antes de seguir.'));
  });
}

async function initialize(config) {
  self.postMessage({progress: 'Preparando la aplicación en tu dispositivo… La primera carga puede tardar unos segundos.'});
  if (config) {
    cloud = config;
    repository = new SupabaseRepository(cloud);
    dbName += ':' + cloud.url + ':' + cloud.session.user.id;
  }
  database = await openDatabase();
  if (!navigator.locks) throw new Error('Actualiza tu navegador: hace falta una versión compatible con almacenamiento local seguro.');
  python = await loadPyodide({indexURL: new URL('./runtime/', self.location.href).href});
  await python.loadPackage('sqlite3', {checkIntegrity: true});
  python.FS.mkdirTree('/data');
  for (const name of ['core.py', 'finance.py', 'browser_api.py', 'cloud_bridge.py']) {
    const response = await fetch(new URL('./python/' + name, self.location.href));
    if (!response.ok) throw new Error('No se pudo cargar el motor contable.');
    python.FS.writeFile('/home/pyodide/' + name, await response.text());
  }
  python.runPython('from browser_api import handle_request, validate_restore');
  python.runPython('from cloud_bridge import export_snapshot, import_snapshot');
}

function snapshotBytes(snapshot, path = '/data/cloud.sqlite3') {
  python.globals.set('cloud_snapshot', JSON.stringify(snapshot));
  python.globals.set('cloud_path', path);
  python.runPython('import_snapshot(cloud_path, cloud_snapshot)');
  return python.FS.readFile(path);
}

async function resolvePending() {
  const pending = await readFile('pending');
  if (!pending) return;
  try {
    const result = await repository.commit(pending);
    try {
      await writeFiles([['real', pending.bytes], ['pending', null], ['meta', {revision: result.revision, updatedAt: new Date().toISOString()}]]);
    } catch {
      throw new Error('La operación está guardada en Supabase, pero no se pudo actualizar la copia de este navegador. Libera espacio y pulsa Actualizar.');
    }
  } catch (error) {
    if (error.conflict || (error.status && error.status !== 401 && error.status !== 403 && error.status < 500)) {
      await writeFiles([['failed-change', pending.bytes], ['pending', null]]);
    }
    throw error;
  }
}

async function refreshCloud() {
  try {
    if (!navigator.onLine) throw Object.assign(new Error('Sin conexión.'), {network: true});
    await resolvePending();
    const remote = await repository.load();
    let bytes;
    if (remote.snapshot) bytes = snapshotBytes(remote.snapshot);
    else {
      try { python.FS.unlink('/data/real.sqlite3'); } catch {}
      callPython('/api/state?mode=real', null);
      bytes = python.FS.readFile('/data/real.sqlite3');
    }
    viewRevision = remote.revision;
    sync = {offline: false, updatedAt: remote.updated_at};
    await writeFiles([['real', bytes], ['meta', {revision: viewRevision, updatedAt: sync.updatedAt}]]);
  } catch (error) {
    const cached = await readFile('real');
    if (!error.network || !cached) throw error;
    const meta = await readFile('meta');
    sync = {offline: true, updatedAt: meta?.updatedAt || null};
    viewRevision = meta?.revision ?? null;
  }
}

async function saveCloud(bytes, restore = false) {
  if (!navigator.onLine || sync.offline) throw new Error('Sin conexión: puedes consultar y descargar respaldos, pero no guardar cambios.');
  if (viewRevision === null) throw new Error('Actualiza las cuentas antes de guardar.');
  if (await readFile('pending')) throw new Error('Hay un guardado pendiente de confirmar. Pulsa Actualizar antes de hacer otra operación.');
  python.FS.writeFile('/data/cloud-candidate.sqlite3', bytes);
  const snapshot = JSON.parse(python.runPython("export_snapshot('/data/cloud-candidate.sqlite3')"));
  const pending = {revision: viewRevision, operationId: crypto.randomUUID(), snapshot, bytes, restore};
  await writeFiles([['pending', pending]]);
  try {
    const result = await repository.commit(pending);
    viewRevision = result.revision;
    sync = {offline: false, updatedAt: new Date().toISOString()};
    try {
      await writeFiles([['real', bytes], ['pending', null], ['meta', {revision: viewRevision, updatedAt: sync.updatedAt}]]);
    } catch {
      throw new Error('La operación está guardada en Supabase, pero no se pudo actualizar la copia de este navegador. Libera espacio y pulsa Actualizar.');
    }
  } catch (error) {
    if (error.conflict || (error.status && error.status !== 401 && error.status !== 403 && error.status < 500)) {
      await writeFiles([['failed-change', bytes], ['pending', null]]);
    }
    throw error;
  }
}

function callPython(path, payload) {
  python.globals.set('request_path', path);
  python.globals.set('request_payload', JSON.stringify(payload));
  return JSON.parse(python.runPython('handle_request(request_path, request_payload)'));
}

async function execute({path, payload, bytes}) {
  const mode = payload?.mode || new URL(path, 'https://local.invalid').searchParams.get('mode') || 'real';
  if (!['real', 'demo'].includes(mode)) throw new Error('Modo inválido.');
  if (path === '/api/session') return {csrf: 'browser-local'};
  if (path === '/api/logout' && cloud) {
    await new Promise((resolve, reject) => {
      const tx = database.transaction('files', 'readwrite');
      tx.objectStore('files').clear(); tx.oncomplete = resolve; tx.onabort = reject;
    });
    return {ok: true};
  }
  if (cloud && mode === 'real' && path.startsWith('/api/state')) await refreshCloud();
  const isCloudWrite = cloud && mode === 'real' && (payload !== null || path === '/api/restore');
  if (isCloudWrite && (!navigator.onLine || sync.offline)) throw new Error('Sin conexión: solo puedes consultar y descargar respaldos.');
  const today = new Date().toLocaleDateString('en-CA');
  const existing = await readFile(mode);
  const backup = await readFile('daily-' + mode);
  const dbPath = '/data/' + mode + '.sqlite3';
  try { python.FS.unlink(dbPath); } catch { /* La primera visita no tiene base. */ }
  if (existing) python.FS.writeFile(dbPath, existing);

  if (cloud && mode === 'real' && (path.startsWith('/api/daily-backup') || path.startsWith('/api/before-restore'))) {
    if (!navigator.onLine) throw new Error('Necesitas conexión para descargar el respaldo de la nube.');
    const snapshot = await repository.backup(path.includes('daily') ? 'daily' : 'restore');
    return {bytes: snapshotBytes(snapshot, '/data/remote-backup.sqlite3'), filename: 'cuentas-respaldo-nube.sqlite3', mime: 'application/octet-stream'};
  }
  if (path.startsWith('/api/failed-change')) {
    const failed = (await readFile('pending'))?.bytes || await readFile('failed-change');
    if (!failed) throw new Error('No hay una operación pendiente para descargar.');
    return {bytes: failed, filename: 'cuentas-operacion-no-confirmada.sqlite3', mime: 'application/octet-stream'};
  }

  if (path.startsWith('/api/daily-backup')) {
    if (!backup) throw new Error('Todavía no hay copia automática. Usa Descargar respaldo.');
    return {bytes: backup.bytes, filename: 'cuentas-copia-automatica.sqlite3', mime: 'application/octet-stream'};
  }
  if (path === '/api/restore') {
    if (!bytes?.length || bytes.length > 50 * 1024 * 1024) throw new Error('Elige un respaldo SQLite de hasta 50 MB.');
    python.FS.writeFile('/data/restore.sqlite3', bytes);
    try {
      python.runPython("validate_restore('/data/restore.sqlite3')");
      const restored = python.FS.readFile('/data/restore.sqlite3');
      if (cloud && mode === 'real') await saveCloud(restored, true);
      const entries = [[mode, restored]];
      if (existing) entries.push(['before-restore-' + mode, {date: today, bytes: existing}]);
      if (!cloud || mode !== 'real') await writeFiles(entries);
      return {ok: true};
    } finally {
      python.FS.unlink('/data/restore.sqlite3');
    }
  }
  if (path.startsWith('/api/before-restore')) {
    const previous = await readFile('before-restore-' + mode);
    if (!previous) throw new Error('No hay una copia anterior a una restauración en este dispositivo.');
    return {bytes: previous.bytes, filename: 'cuentas-antes-restaurar.sqlite3', mime: 'application/octet-stream'};
  }
  const result = callPython(path, payload);
  const current = python.FS.readFile(dbPath);
  if (cloud && mode === 'real' && payload !== null && !path.startsWith('/api/csv-preview')) await saveCloud(current);
  const entries = [[mode, current]];
  if (!backup || backup.date !== today) entries.push(['daily-' + mode, {date: today, bytes: existing || current}]);
  if (!cloud || mode !== 'real') await writeFiles(entries);
  if (result.download_path) {
    result.bytes = python.FS.readFile(result.download_path);
    python.FS.unlink(result.download_path);
    delete result.download_path;
  }
  if (cloud && mode === 'real') {
    result.__sync = sync;
    if (result.data_path) result.data_path = 'Cuenta privada en Supabase · copia local para consulta';
  }
  return result;
}

self.onmessage = ({data}) => {
  queue = queue.then(async () => {
    try {
      initialization ||= initialize(data.cloud);
      await initialization;
      if (cloud) {
        if (data.cloud?.session?.user?.id !== cloud.session.user.id) throw new Error('La cuenta ha cambiado. Recarga la aplicación.');
        cloud.session = data.cloud.session;
      }
      const result = await navigator.locks.request(dbName, () => execute(data));
      self.postMessage({id: data.id, result});
    } catch (error) {
      let message = error.message || 'No se pudo completar la operación.';
      if (error.name === 'PythonError' || message.includes('Traceback (most recent call last)')) {
        message = message.trim().split('\n').at(-1).replace(/^[\w.]+(?:Error|Exception):\s*/, '');
      }
      self.postMessage({id: data.id, error: message});
    }
  });
};
