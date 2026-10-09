/* Python y SQLite se ejecutan aquí; ningún dato financiero sale del dispositivo. */
importScripts('./runtime/pyodide.js');

const dbName = 'mis-cuentas:' + new URL('.', self.location.href).pathname;
let database;
let python;
let initialization;
let queue = Promise.resolve();

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

async function initialize() {
  self.postMessage({progress: 'Preparando la aplicación en tu dispositivo… La primera carga puede tardar unos segundos.'});
  database = await openDatabase();
  if (!navigator.locks) throw new Error('Actualiza tu navegador: hace falta una versión compatible con almacenamiento local seguro.');
  python = await loadPyodide({indexURL: new URL('./runtime/', self.location.href).href});
  await python.loadPackage('sqlite3', {checkIntegrity: true});
  python.FS.mkdirTree('/data');
  for (const name of ['core.py', 'finance.py', 'browser_api.py']) {
    const response = await fetch(new URL('./python/' + name, self.location.href));
    if (!response.ok) throw new Error('No se pudo cargar el motor contable.');
    python.FS.writeFile('/home/pyodide/' + name, await response.text());
  }
  python.runPython('from browser_api import handle_request, validate_restore');
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
  const today = new Date().toLocaleDateString('en-CA');
  const existing = await readFile(mode);
  const backup = await readFile('daily-' + mode);
  const dbPath = '/data/' + mode + '.sqlite3';
  try { python.FS.unlink(dbPath); } catch { /* La primera visita no tiene base. */ }
  if (existing) python.FS.writeFile(dbPath, existing);

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
      const entries = [[mode, restored]];
      if (existing) entries.push(['before-restore-' + mode, {date: today, bytes: existing}]);
      await writeFiles(entries);
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
  const entries = [[mode, current]];
  if (!backup || backup.date !== today) entries.push(['daily-' + mode, {date: today, bytes: existing || current}]);
  await writeFiles(entries);
  if (result.download_path) {
    result.bytes = python.FS.readFile(result.download_path);
    python.FS.unlink(result.download_path);
    delete result.download_path;
  }
  return result;
}

self.onmessage = ({data}) => {
  queue = queue.then(async () => {
    try {
      initialization ||= initialize();
      await initialization;
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
