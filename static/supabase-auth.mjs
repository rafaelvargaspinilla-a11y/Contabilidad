import './supabase-rest.js';

export class SupabaseAuth {
  constructor(config) {
    this.config = config;
    this.key = 'miscuentas-auth:' + config.url + ':' + new URL('.', import.meta.url).pathname;
    this.client = new globalThis.SupabaseRepository(config);
    this.channel = new BroadcastChannel(this.key);
    this.refreshing = null;
    this.onSignOut = null;
    this.channel.onmessage = ({data}) => {
      if (data === 'logout') { this.session = null; localStorage.removeItem(this.key); this.onSignOut?.(); }
    };
    try { this.session = JSON.parse(localStorage.getItem(this.key)); } catch { this.session = null; }
  }

  save(session) {
    this.session = {...session, expires_at: session.expires_at || Math.floor(Date.now()/1000) + session.expires_in};
    localStorage.setItem(this.key, JSON.stringify(this.session));
    return this.session;
  }

  async login(email, password) {
    const session = await this.client.call('/auth/v1/token?grant_type=password', {email, password}, null);
    return this.save(session);
  }

  async ensureSession() {
    if (!this.session) throw new Error('Inicia sesión para acceder a tus cuentas.');
    const readLatest = () => {
      try {
        const latest = JSON.parse(localStorage.getItem(this.key));
        if (latest?.user?.id === this.session.user?.id && latest.expires_at >= this.session.expires_at) this.session = latest;
      } catch {}
    };
    readLatest();
    if (navigator.onLine && this.session.expires_at < Date.now()/1000 + 60) {
      const refresh = async () => {
        readLatest();
        if (this.session.expires_at >= Date.now()/1000 + 60) return;
        try {
          this.save(await this.client.call('/auth/v1/token?grant_type=refresh_token', {refresh_token: this.session.refresh_token}, null));
        } catch (error) { if (!error.network || !this.session?.user?.id) throw error; }
      };
      this.refreshing ||= (navigator.locks ? navigator.locks.request(this.key + ':refresh', refresh) : refresh())
        .finally(() => { this.refreshing = null; });
      await this.refreshing;
    }
    return this.session;
  }

  async verify() {
    const session = await this.ensureSession();
    if (navigator.onLine) {
      try {
        const user = await this.client.call('/auth/v1/user', undefined, session.access_token, 'GET');
        this.save({...session, user});
      } catch (error) {
        if (!error.network || !this.session.user?.id) throw error;
      }
    }
    if (!this.session.user?.id) throw new Error('No se pudo identificar tu cuenta.');
    return this.session;
  }

  async recover(email) {
    const redirect = new URL('.', import.meta.url).href;
    await this.client.call('/auth/v1/recover?redirect_to=' + encodeURIComponent(redirect), {email}, null);
  }

  async changePassword(password) {
    await this.client.call('/auth/v1/user', {password}, this.session.access_token, 'PUT');
  }

  async logout() {
    const session = this.session;
    this.session = null;
    localStorage.removeItem(this.key);
    this.channel.postMessage('logout');
    if (session && navigator.onLine) {
      try { await this.client.call('/auth/v1/logout?scope=local', {}, session.access_token); } catch { /* La sesión local ya se ha eliminado. */ }
    }
  }

  async acquire() {
    const fragment = new URLSearchParams(location.hash.slice(1));
    const recovery = fragment.get('type') === 'recovery' && fragment.has('access_token');
    if (fragment.has('access_token')) {
      this.save({access_token: fragment.get('access_token'), refresh_token: fragment.get('refresh_token'), expires_in: Number(fragment.get('expires_in') || 3600)});
      history.replaceState(null, '', location.pathname + location.search);
    }
    if (!recovery && this.session) {
      try { return await this.verify(); } catch { this.session = null; localStorage.removeItem(this.key); }
    }
    const panel = document.createElement('main');
    panel.className = 'auth-screen';
    panel.innerHTML = `<section class="panel"><h1>Mis cuentas</h1><p>${recovery ? 'Elige una nueva contraseña para tu cuenta.' : 'Accede a las mismas cuentas desde tu móvil y tu ordenador.'}</p><form id="cloud-login"><div class="form-grid">${recovery ? '' : '<div class="field wide"><label for="cloud-email">Correo electrónico</label><input id="cloud-email" name="email" type="email" autocomplete="username" required></div>'}<div class="field wide"><label for="cloud-password">${recovery ? 'Nueva contraseña' : 'Contraseña'}</label><input id="cloud-password" name="password" type="password" autocomplete="${recovery ? 'new-password' : 'current-password'}" minlength="8" required></div></div><div class="error" role="alert"></div><div class="form-actions"><button type="submit" class="button primary">${recovery ? 'Guardar contraseña' : 'Entrar'}</button></div></form>${recovery ? '' : '<button type="button" class="button quiet" id="cloud-recover">He olvidado mi contraseña</button>'}<p class="small">Tus datos son privados. Usa tu cuenta creada en Supabase para esta aplicación.</p></section>`;
    document.querySelector('.sidebar').hidden = true;
    document.querySelector('.shell').hidden = true;
    document.body.append(panel);
    return new Promise(resolve => {
      const form = panel.querySelector('form');
      const error = panel.querySelector('.error');
      form.addEventListener('submit', async event => {
        event.preventDefault();
        const button = form.querySelector('button');
        button.disabled = true;
        error.textContent = '';
        try {
          const values = new FormData(form);
          if (recovery) {
            await this.verify();
            await this.changePassword(values.get('password'));
          } else await this.login(values.get('email'), values.get('password'));
          const session = await this.verify();
          form.reset(); panel.remove();
          document.querySelector('.sidebar').hidden = false;
          document.querySelector('.shell').hidden = false;
          resolve(session);
        } catch (e) { error.textContent = e.message; }
        finally { button.disabled = false; }
      });
      panel.querySelector('#cloud-recover')?.addEventListener('click', async event => {
        const email = panel.querySelector('#cloud-email');
        if (!email.reportValidity()) return;
        event.target.disabled = true;
        try {
          await this.recover(email.value);
          error.textContent = 'Si existe una cuenta con ese correo, recibirás un enlace para recuperar el acceso.';
        } catch (e) { error.textContent = e.message; }
        finally { event.target.disabled = false; }
      });
    });
  }
}
