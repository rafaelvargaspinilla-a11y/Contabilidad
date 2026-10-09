/* Cliente REST pequeño: credenciales únicamente al proyecto configurado. */
globalThis.SupabaseRepository = class {
  constructor(config) { this.config = config; }

  async call(path, body, token = this.config.session?.access_token, method = 'POST') {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(this.config.url + path, {
        method, signal: controller.signal, cache: 'no-store', credentials: 'omit', redirect: 'error',
        headers: {'apikey': this.config.publishableKey, ...(token ? {'Authorization': 'Bearer ' + token} : {}), 'Content-Type': 'application/json'},
        ...(body === undefined ? {} : {body: JSON.stringify(body)}),
      });
      const data = response.status === 204 ? null : await response.json();
      if (!response.ok) {
        const code = data?.message || data?.msg || data?.error_description || data?.error || '';
        let message = 'No se pudo completar la operación en Supabase.';
        if (code.includes('MC_CONFLICT')) message = 'Las cuentas cambiaron en otro dispositivo. Actualiza los datos y revisa la operación antes de volver a guardar.';
        else if (code.includes('MC_NO_BACKUP')) message = 'Todavía no hay un respaldo de ese tipo en la nube.';
        else if (code.includes('MC_INVALID') || data?.code?.startsWith('23')) message = 'Las cuentas contienen datos o referencias inválidas; no se guardó la operación.';
        else if (response.status === 401 || response.status === 403) message = 'Tu sesión ha caducado o no tiene permiso. Vuelve a iniciar sesión.';
        else if (path.startsWith('/auth/')) message = 'No se pudo acceder. Comprueba el correo, la contraseña y la configuración de acceso.';
        const error = new Error(message);
        error.status = response.status;
        error.conflict = code.includes('MC_CONFLICT');
        error.noBackup = code.includes('MC_NO_BACKUP');
        throw error;
      }
      return data;
    } catch (error) {
      if (error.name === 'AbortError' || error instanceof TypeError) {
        const unavailable = new Error('No se pudo confirmar la conexión con Supabase. Si estabas guardando, pulsa Actualizar para comprobar el resultado antes de repetir la operación.');
        unavailable.network = true;
        throw unavailable;
      }
      throw error;
    } finally { clearTimeout(timer); }
  }

  load() { return this.call('/rest/v1/rpc/mc_load', {}); }
  commit(pending) {
    return this.call('/rest/v1/rpc/mc_commit', {
      p_expected_revision: pending.revision, p_operation_id: pending.operationId,
      p_snapshot: pending.snapshot, p_restore: pending.restore || false,
    });
  }
  backup(kind) { return this.call('/rest/v1/rpc/mc_backup', {p_kind: kind}); }
};
