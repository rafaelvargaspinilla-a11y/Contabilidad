'use strict';
import {assignImportArea, assignImportCategory} from './import-utils.mjs';
import {businessUI} from './business-ui.mjs';
import {browserMode, downloadFile} from './transport.mjs';
const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const euro = n => new Intl.NumberFormat('es-ES',{style:'currency',currency:'EUR'}).format((n||0)/100);
const number = n => ((n||0)/100).toFixed(2);
const AREAS = {all:'Vista conjunta',academia:'Academia',baile:'Baile',personal:'Personal'};
const KINDS = {income:'Ingreso',expense:'Gasto / devolución',distribution:'Reparto de resultado',transfer:'Traspaso',funding:'Aportación',reimbursement:'Reembolso',remuneration:'Retribución'};
const today = new Date();
const localDay = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const modeKey = browserMode ? 'miscuentas-mode:' + new URL('.', import.meta.url).pathname : 'miscuentas-mode';
const U = {area:'all',page:'summary',mode:localStorage.getItem(modeKey)||'real',month:localDay(today).slice(0,7),data:null,csrf:'',selected:new Set(),csv:null,preview:null};
const pages = {summary:'Resumen',activity:'Actividad',courses:'Asignaturas',transactions:'Banco',import:'Importar extracto',settlements:'Liquidaciones',settings:'Configuración',ai:'Asistente local'};
if(browserMode) delete pages.ai;
const B=businessUI({U,$,$$,esc,euro,number,field,button,head,stat,areaOptions,accountOptions,categoryOptions,opts,openDialog,api,load,render,toast});

async function api(path,p){
  if(browserMode) return globalThis.misCuentasBrowser.request(path,p ? {...p,mode:U.mode} : null);
  const options = p ? {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':U.csrf},body:JSON.stringify({...p,mode:U.mode})} : {};
  const r=await fetch(path,options); const data=await r.json();
  if(!r.ok) throw new Error(data.error||'No se pudo completar la operación.');
  return data;
}
async function load(){
  U.data=await api(`/api/state?mode=${U.mode}&month=${U.month}`); render();
}
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,4500);}
function reportError(err,form){ const target=form?.querySelector('.error');if(target)target.textContent=err.message;else toast(err.message); }
async function mutate(path,p,message='Guardado'){await api(path,p);await load();toast(message);}
function opts(items,current,value='id',label='name'){return items.map(i=>`<option value="${esc(i[value])}" ${String(current)===String(i[value])?'selected':''}>${esc(i[label])}</option>`).join('');}
function areaOptions(current,all=false){return Object.entries(AREAS).filter(([a])=>all||a!=='all').map(([a,n])=>`<option value="${a}" ${a===current?'selected':''}>${n}</option>`).join('');}
function accountOptions(current){return U.data.accounts.map(a=>`<option value="${a.id}" ${a.id===current?'selected':''}>${esc(a.name)} · ${AREAS[a.area]}</option>`).join('');}
function categoryOptions(area,kind,current){return '<option value="">Pendiente de categoría</option>'+opts(U.data.categories.filter(c=>c.area===area&&c.kind===kind),current);}
let fieldSerial=0;
function field(label,input,wide=false,help=''){
 const tag=input.match(/<(?:input|select|textarea)\b[^>]*>/)?.[0];
 let id=tag?.match(/\bid="([^"]+)"/)?.[1];
 if(tag&&!id){id=`field-${++fieldSerial}`;input=input.replace(tag,tag.replace(/>$/,` id="${id}">`));}
 return `<div class="field ${wide?'wide':''}"><label${id?` for="${id}"`:''}>${label}</label>${input}${help?`<small>${help}</small>`:''}</div>`;
}
function button(label,action,cls='',extra=''){return `<button type="button" class="button ${cls}" data-action="${action}" ${extra}>${label}</button>`;}
function badge(area){return `<span class="area-badge ${area}">${AREAS[area][0]}</span>`;}
function head(title,description,actions=''){return `<div class="page-head"><div><div class="eyebrow">${AREAS[U.area]} · ${monthLabel(U.month)}</div><h1>${title}</h1><p class="hint">${description}</p></div><div class="action-row">${actions}</div></div>`;}
function monthLabel(month){return new Date(month+'-15T12:00:00').toLocaleDateString('es-ES',{month:'long',year:'numeric'});}
function stat(label,value,sub,focus=false){return `<div class="stat ${focus?'focus':''}"><div class="stat-label">${label}</div><div class="stat-value">${euro(value)}</div><div class="sub">${sub}</div></div>`;}
function monthRows(area=U.area,month=U.month){return U.data.transactions.filter(t=>t.date.startsWith(month)&&(area==='all'||t.area===area));}
function amounts(rows,area){
 const effective=rows.filter(t=>area!=='all'||!t.link_id);
 const income=effective.filter(t=>t.kind==='income'||t.kind==='remuneration'&&t.amount>0).reduce((a,t)=>a+t.amount,0);
 const expense=-effective.filter(t=>t.kind==='expense'||t.kind==='remuneration'&&t.amount<0).reduce((a,t)=>a+t.amount,0);
 const received=area==='personal'?rows.filter(t=>t.kind==='distribution'&&t.amount>0).reduce((a,t)=>a+t.amount,0):0;
 return {income,expense,received,result:income+received-expense};
}
function balance(account){const end=U.month+'-31';return (account.opening_date<=end?account.opening:0)+U.data.transactions.filter(t=>t.account_id===account.id&&t.date<=end).reduce((a,t)=>a+t.amount,0);}
function empty(title,text,actions=''){return `<div class="empty"><div class="empty-symbol">↗</div><h2>${title}</h2><p>${text}</p><div class="action-row" style="justify-content:center;margin-top:18px">${actions}</div></div>`;}

function render(){
 $('#areas').innerHTML=Object.entries(AREAS).map(([a,n])=>`<button class="side-button ${U.area===a?'active':''}" data-area="${a}"><span class="area-dot"></span>${n}</button>`).join('');
 $('#navigation').innerHTML=Object.entries(pages).map(([p,n])=>`<button class="side-button ${U.page===p?'active':''}" data-page="${p}">${n}</button>`).join('');
 $('#breadcrumb').textContent=`${AREAS[U.area]} / ${pages[U.page]}`;
 $('#demo-banner').hidden=U.mode!=='demo';$('#mode').value=U.mode;$('#month').value=U.month;
 const views={summary:B.summary,activity:B.activity,courses:B.courses,settlements:B.settlements,transactions:renderTransactions,import:renderImport,settings:renderSettings,ai:renderAI};
 $('#content').innerHTML=views[U.page]();
 bindContent();B.bind();
}

function renderTransactions(){
 return head('Cada movimiento, en su lugar.','El área indica a qué actividad pertenece; la cuenta indica dónde se ha cobrado o pagado.',button('Pago interno','new-move')+button('Exportar CSV','export'))+
 `<div class="filters"><input id="tx-search" placeholder="Buscar concepto, categoría o cuenta" aria-label="Buscar movimientos"><select id="tx-kind" aria-label="Tipo"><option value="">Todos los tipos</option>${Object.entries(KINDS).map(([k,n])=>`<option value="${k}">${n}</option>`).join('')}<option value="uncategorized">Sin categoría</option></select>${button('Vincular 2 seleccionados','link-selected')}</div><div class="panel"><div class="sub" id="tx-count"></div><div id="tx-table" class="table-wrap"></div></div><div class="inline-note">Si importas las dos mitades de un pago entre tus cuentas, selecciónalas y pulsa «Vincular». Así no se contarán como ingreso y gasto externos. Primero corrige el área si es necesario.</div>`;
}
function fillTransactions(){
 const search=($('#tx-search')?.value||'').toLocaleLowerCase();const kind=$('#tx-kind')?.value||'';
 const rows=monthRows().filter(t=>`${t.description} ${t.category||''} ${t.account}`.toLocaleLowerCase().includes(search)&&(!kind||(kind==='uncategorized'?!t.category_id&&['income','expense'].includes(t.kind):t.kind===kind)));
 $('#tx-count').textContent=`${rows.length} movimientos · ${U.selected.size} seleccionados${rows.length>500?' · Se muestran los primeros 500; usa los filtros':''}`;
 $('#tx-table').innerHTML=rows.length?`<table><thead><tr><th></th><th>FECHA</th><th>CONCEPTO / CUENTA</th><th>ÁREA</th><th>CATEGORÍA / TIPO</th><th class="num">IMPORTE</th><th></th></tr></thead><tbody>${rows.slice(0,500).map(t=>`<tr class="${U.selected.has(t.id)?'selected-row':''}"><td><input type="checkbox" data-select-tx="${t.id}" ${U.selected.has(t.id)?'checked':''} aria-label="Seleccionar ${esc(t.description)}"></td><td>${t.date.split('-').reverse().join('/')}</td><td><strong>${esc(t.description)}</strong><div class="sub">${esc(t.account)}${t.link_id?' · ↔ Vinculado':''}</div></td><td>${AREAS[t.area]}</td><td>${esc(t.category||KINDS[t.kind])}${!t.category_id&&['income','expense'].includes(t.kind)?'<div class="sub warning-cell">Sin categoría</div>':''}</td><td class="num ${t.amount>=0?'positive':''}">${euro(t.amount)}</td><td>${!t.link_id&&['income','expense'].includes(t.kind)?button('Conciliar','reconcile-bank','compact',`data-id="${t.id}"`)+(!U.data.finance.links.some(l=>l.tx_id===t.id)?button('Clasificar','classify-bank','compact',`data-id="${t.id}"`):''):''}${button('Anular','delete-tx','quiet compact danger',`data-id="${t.id}"`)}</td></tr>`).join('')}</tbody></table>`:empty('Sin movimientos con esos filtros.','Añade un movimiento o importa un extracto para este mes.',button('Añadir movimiento','new-tx','primary'));
}

function renderSettings(){
 const accounts=U.data.accounts.filter(a=>U.area==='all'||a.area===U.area);
 return head('Una estructura que se adapta a ti.','Configura cuentas, categorías y reglas. Puedes registrar todos los gastos de socios y profesores.',button('Nueva cuenta','new-account')+button('Nueva categoría','new-category','primary'))+
 `<div class="account-grid">${accounts.map(a=>`<div class="panel"><div class="area-label">${badge(a.area)}${esc(a.name)}</div><div class="account-balance">${euro(balance(a))}</div><div class="sub">${AREAS[a.area]} · saldo a cierre de mes<br>Saldo inicial: ${euro(a.opening)} · ${a.opening_date}</div><div style="margin-top:12px">${button('Configurar','edit-account','compact',`data-id="${a.id}"`)}</div></div>`).join('')}</div>`+
 `<div class="tools-grid"><div class="panel"><div class="panel-head"><div><h2>Categorías</h2><div class="sub">Separadas por área y por ingreso/gasto.</div></div></div>${['academia','baile','personal'].filter(a=>U.area==='all'||a===U.area).map(a=>`<details ${U.area===a?'open':''}><summary>${AREAS[a]} · ${U.data.categories.filter(c=>c.area===a).length} categorías</summary><table><tbody>${U.data.categories.filter(c=>c.area===a).map(c=>`<tr><td>${esc(c.name)}</td><td class="num"><span class="pill">${c.kind==='income'?'Ingreso':'Gasto'}</span></td></tr>`).join('')}</tbody></table></details>`).join('')}</div><div class="panel"><div class="panel-head"><div><h2>Reglas de importación</h2><div class="sub">Se aplican a nuevos CSV del área elegida.</div></div>${button('Nueva','new-rule','compact')}</div>${U.data.rules.length?`<table><tbody>${U.data.rules.map(r=>`<tr><td>Contiene <strong>${esc(r.term)}</strong><div class="sub">${AREAS[r.area]} → ${esc(r.category)}</div></td><td>${button('Eliminar','delete-rule','quiet compact',`data-id="${r.id}"`)}</td></tr>`).join('')}</tbody></table>`:'<p>Crea reglas para comercios habituales. Si hay varias coincidencias, se usa la que contiene el texto más específico.</p>'}</div></div>`+
 `<div class="panel"><div class="panel-head"><div><h2>Tus datos y tus copias</h2><div class="sub">Se guardan al confirmar cada operación. Hay una copia diaria al iniciar.</div></div><div class="action-row">${button('Descargar respaldo','backup')}${button('Exportar movimientos','export')}</div></div><div class="mono">${esc(U.data.data_path)}</div><p class="small">${browserMode ? 'Este navegador guarda tus cuentas; no se sincronizan con otros dispositivos. Borrar los datos del sitio o usar el modo privado puede hacer que las pierdas. Descarga un respaldo y guárdalo en un lugar seguro.' : 'El respaldo contiene todas las cuentas, reglas, porcentajes e historial. La guía LEEME explica cómo restaurarlo. Los archivos locales no están cifrados por la app; utiliza el cifrado del disco y de tus copias.'}</p>${browserMode ? `<div class="action-row">${button('Descargar copia automática','daily-backup')}${button('Copia anterior a restaurar','before-restore')}</div><div class="field restore-field"><label for="restore-file">Restaurar un respaldo en ${U.mode==='real'?'Mis datos':'el ejemplo'}</label><input id="restore-file" type="file" accept=".sqlite3,.sqlite,.db"><small>Sustituye las cuentas de este dispositivo. Se conserva una copia previa; no se mezclan las bases.</small></div>${button('Restaurar respaldo','restore','danger')}` : ''}</div>`;
}

function defaultImportActivity(r){
 const method=r.area==='academia'?(r.kind==='income'?'own':'shared'):'individual';
 r.activity={method,my_percent:r.area==='academia'?U.data.finance.preferences.my_share/100:50,course_id:''};
 r.treatment='new';r.entry_id='';
}
function importClassification(r,i){
 if(r.error)return '<td colspan="4">—</td>';
 const activity=r.activity;
 const fieldSelect=(name,html)=>`<select data-csv-field="${name}" data-index="${i}" aria-label="${name} fila ${r.row}">${html}</select>`;
 const methods=r.area==='academia'&&r.kind==='income'?[['own','Propia · 100 %'],['external','Profesor externo']]:r.area==='personal'?[['individual','Individual · 100 %']]:[['individual','Individual · 100 %'],['shared',r.area==='baile'?'Compartido · 50 %':'Gasto compartido']];
 const courses=U.data.finance.courses.filter(c=>c.ownership===activity.method&&(c.semester===1?r.date.slice(0,7)>=c.year+'-09'&&r.date.slice(0,7)<=c.year+'-12':r.date.slice(0,7)>=(c.year+1)+'-01'&&r.date.slice(0,7)<=(c.year+1)+'-05'));
 const candidates=U.data.finance.entries.filter(e=>e.area===r.area&&e.holder==='me'&&e.pending>=Math.abs(r.amount)&&(e.kind==='income'||e.refund?r.amount>0:r.amount<0));
 const route=r.entry_id?'entry:'+r.entry_id:r.treatment;
 return `<td>${fieldSelect('area',areaOptions(r.area))}${fieldSelect('category',categoryOptions(r.area,r.kind,r.category_id))}</td><td>${fieldSelect('method',methods.map(([v,n])=>`<option value="${v}" ${activity.method===v?'selected':''}>${n}</option>`).join(''))}${['shared','external'].includes(activity.method)?`<label class="small">Tu % <input type="number" min="0" max="100" step="0.01" value="${activity.my_percent}" data-csv-field="my_percent" data-index="${i}" aria-label="Tu porcentaje fila ${r.row}"></label>`:''}</td><td>${r.area==='academia'&&r.kind==='income'?fieldSelect('course_id','<option value="">Sin asignatura</option>'+opts(courses,activity.course_id)):'—'}</td><td>${fieldSelect('route',`<option value="new" ${route==='new'?'selected':''}>Crear actividad</option><option value="bank_only" ${route==='bank_only'?'selected':''}>Solo banco / pendiente de vincular</option>`+candidates.map(e=>`<option value="entry:${e.id}" ${route==='entry:'+e.id?'selected':''}>Vincular: ${esc(e.description)} · ${e.period} · pendiente ${euro(e.pending)}</option>`).join(''))}</td>`;
}
function fillImportRows(){
 const size=100,page=U.preview.page||0,rows=U.preview.rows;
 $('#csv-table-body').innerHTML=rows.slice(page*size,(page+1)*size).map((r,j)=>{const i=page*size+j;return `<tr><td><input type="checkbox" data-import-row="${i}" ${r.selected?'checked':''} ${r.error?'disabled':''} aria-label="Importar fila ${r.row}"></td><td>${r.row}</td><td>${esc(r.date||'')}</td><td class="import-description">${esc(r.description||'')}</td><td class="num">${r.amount!==undefined?euro(r.amount):''}</td>${importClassification(r,i)}<td class="${r.error?'negative':r.duplicate?'warning-cell':''}">${esc(r.error||(r.duplicate?'Posible duplicado':r.category_id?'Clasificado':'Sin categoría'))}</td></tr>`;}).join('');
 $('#csv-page').textContent=`Filas ${rows.length?page*size+1:0}–${Math.min(rows.length,(page+1)*size)} de ${rows.length}`;
 $('[data-action="csv-prev"]').disabled=page===0;$('[data-action="csv-next"]').disabled=(page+1)*size>=rows.length;
 updateImportCount();
}
function updateImportRow(input){
 const i=Number(input.dataset.index),name=input.dataset.csvField;let r=U.preview.rows[i];
 if(name==='area'){r=assignImportArea(r,input.value,U.data.categories,U.data.rules);defaultImportActivity(r);}
 if(name==='category')r=assignImportCategory(r,input.value,U.data.categories);
 if(name==='method'){r.activity.method=input.value;r.activity.course_id='';r.activity.my_percent=r.area==='academia'?U.data.finance.preferences.my_share/100:50;}
 if(name==='my_percent')r.activity.my_percent=input.value;
 if(name==='course_id')r.activity.course_id=input.value;
 if(name==='route'){r.entry_id=input.value.startsWith('entry:')?input.value.slice(6):'';r.treatment=r.entry_id?'existing':input.value;}
 U.preview.rows[i]=r;
 const scroll=$('.preview-table').scrollTop;
 fillImportRows();$('.preview-table').scrollTop=scroll;
}
function renderImport(){
 let html=head('Importa y clasifica antes de guardar.','Cada fila puede pertenecer a Academia, Baile o Personal, aunque salga de la misma cuenta bancaria.');
 html+=`<div class="panel"><div class="step-number">01 / ARCHIVO LOCAL</div><input type="file" id="csv-file" accept=".csv,.tsv,.txt" aria-label="Elegir extracto"><div class="form-grid">${field('Codificación','<select id="csv-encoding"><option value="utf-8">UTF-8</option><option value="windows-1252">Windows / Latin-1</option></select>')}${field('Filas antes de la cabecera','<input id="csv-skip" type="number" min="0" max="100" value="0">')}${field('Separador','<select id="csv-delimiter"><option value="">Detectar</option><option value=";">Punto y coma</option><option value=",">Coma</option><option value="tab">Tabulación</option></select>')}</div><div class="form-actions">${button('Leer columnas','read-csv','primary')}</div></div>`;
 if(U.csv?.headers){
 const h=U.csv.headers,guess=names=>h.find(x=>names.some(n=>x.toLowerCase().includes(n)))||'';
 const select=(id,value)=>`<select id="map-${id}"><option value="">Sin usar</option>${h.map(x=>`<option value="${esc(x)}" ${x===value?'selected':''}>${esc(x)}</option>`).join('')}</select>`;
 html+=`<div class="panel"><div class="step-number">02 / COLUMNAS Y VALORES INICIALES</div><h2>${esc(U.csv.name)}</h2><p>${U.csv.count} filas. El área inicial se puede cambiar en cada fila.</p><div class="form-grid">${field('Cuenta bancaria',`<select id="csv-account">${accountOptions(U.area==='all'?'personal':U.area)}</select>`)}${field('Área inicial',`<select id="csv-area">${areaOptions(U.area==='all'?'personal':U.area)}</select>`)}${field('Fecha',select('date',guess(['fecha','date'])))}${field('Formato de fecha','<select id="csv-date-format"><option value="ymd">Año-mes-día · 2026-09-23 (también con hora)</option><option value="dmy" selected>Día/mes/año · 23/09/2026</option><option value="mdy">Mes/día/año · 09/23/2026</option></select>',false,'Las fechas ISO con o sin hora se reconocen también con las otras opciones.')}${field('Concepto',select('description',guess(['concepto','description','comercio','payee'])))}${field('Importe con signo',select('amount',guess(['importe','amount'])))}${field('Entradas (si no usas importe con signo)',select('inflow',guess(['abono','ingreso','inflow'])))}${field('Salidas (si no usas importe con signo)',select('outflow',guess(['cargo','debito','outflow'])))}${field('Notas',select('notes',guess(['notas','notes'])))}${field('ID bancario único',select('bank_id',guess(['transaction id','id bancario'])))}</div><label class="checkbox"><input id="csv-flip" type="checkbox">Invertir signo del importe</label><div class="form-actions">${button('Previsualizar movimientos','preview-csv','primary')}</div></div>`;
 }
 if(U.preview)html+=`<div class="panel" id="preview-panel"><div class="step-number">03 / CLASIFICAR Y GUARDAR</div><div class="panel-head"><div><h2>Área, categoría y reparto por movimiento</h2><p class="small">Los posibles duplicados están desmarcados. La cuenta bancaria se conserva aunque cambies el área.</p></div><span class="pill" id="import-count"></span></div><div class="inline-note">El importe del CSV es dinero real del banco. Si una factura tiene retención, vincúlalo a la factura ya registrada con su bruto e IRPF. Un registro nuevo importado empieza con retención 0; puedes completar después el bruto y la retención. Los pagos entre tus cuentas se vinculan desde Banco.</div><div class="preview-table"><table><thead><tr><th></th><th>FILA</th><th>FECHA</th><th>CONCEPTO</th><th>IMPORTE</th><th>ÁREA / CATEGORÍA</th><th>REPARTO</th><th>ASIGNATURA</th><th>TRATAMIENTO</th><th>ESTADO</th></tr></thead><tbody id="csv-table-body"></tbody></table></div><div class="action-row"><span id="csv-page" class="sub"></span>${button('Anterior','csv-prev','compact')}${button('Siguiente','csv-next','compact')}</div><div class="form-actions">${button('Importar seleccionados','confirm-import','primary')}</div></div>`;
 html+=`<div class="panel"><h2>Importaciones anteriores</h2><div class="table-wrap"><table><thead><tr><th>ARCHIVO</th><th>FECHA</th><th>ACTIVOS</th><th></th></tr></thead><tbody>${U.data.batches.map(b=>`<tr><td>${esc(b.name)}</td><td>${b.created.slice(0,16).replace('T',' ')}</td><td>${b.count}</td><td>${b.active?button('Deshacer lote','undo-import','quiet compact',`data-id="${b.id}"`):'Anulado'}</td></tr>`).join('')||'<tr><td colspan="4">Sin importaciones.</td></tr>'}</tbody></table></div></div>`;
 return html;
}

function renderAI(){
 return head('Una segunda mirada, en local.','El asistente recibe los totales calculados del mes. Puede explicarlos, pero no modifica tus cuentas.')+
 `<div class="panel"><h2>Conecta tu Ollama local</h2><p>Instala Ollama por separado y descarga <code>qwen3.5:4b</code>. Configura Ollama en modo exclusivamente local. Esta app llama únicamente a <code>127.0.0.1:11434</code>, ignora proxies y no admite modelos cloud.</p><div class="inline-note">Se envían a tu Ollama solo los totales de las tres áreas del mes elegido y tu pregunta. No se envían conceptos, cuentas, nombres de socios ni extractos.</div><form data-form="ai"><div class="form-grid">${field('Modelo local','<select name="model"><option>qwen3.5:4b</option><option>qwen3.5:9b</option><option>qwen3:4b</option><option>qwen3:8b</option></select>')}${field('Periodo',`<input value="${monthLabel(U.month)}" disabled>`)}${field('Tu pregunta','<textarea name="question" placeholder="Explica la diferencia entre el resultado de academia y mi margen personal este mes." required></textarea>',true)}</div><div class="error"></div><div class="form-actions"><button class="button primary" type="submit">Consultar en mi Mac</button></div></form><div class="assistant-answer" id="ai-answer" hidden></div><p class="small">La respuesta puede contener errores de interpretación. Las cifras de los paneles proceden del registro y son la referencia. No se ha instalado ni descargado ningún modelo con esta aplicación.</p></div>`;
}

function openDialog(title,body,form,extra=''){
 $('#modal-content').innerHTML=`<div class="dialog-head"><h2>${title}</h2><button type="button" class="close" data-action="close-modal" aria-label="Cerrar">×</button></div><form data-form="${form}" ${extra}>${body}<div class="error"></div><div class="form-actions">${button('Cancelar','close-modal')}<button type="submit" class="button primary">Guardar</button></div></form>`;
 $('#modal').showModal();
}
function entryDialog(tx){
 const a=tx?.area||(U.area==='all'?'personal':U.area),k=tx?.kind||'expense';
 const p=U.data.people.filter(x=>!x.is_me);
 const body=`<div class="form-grid">${field('Área',`<select name="area" id="entry-area">${areaOptions(a)}</select>`)}${field('Tipo',`<select name="kind" id="entry-kind"><option value="expense" ${k==='expense'?'selected':''}>Gasto / devolución</option><option value="income" ${k==='income'?'selected':''}>Ingreso</option><option value="distribution" ${k==='distribution'?'selected':''}>Reparto a otra persona</option></select>`)}${field('Fecha',`<input name="date" type="date" value="${tx?.date||U.month+'-'+String(Math.min(today.getDate(),28)).padStart(2,'0')}" required>`)}${field('Importe (€)',`<input name="value" inputmode="decimal" placeholder="0,00" value="${tx?number(Math.abs(tx.amount)):''}" required>`)}${field('Cuenta donde se mueve el dinero',`<select name="account_id" id="entry-account">${accountOptions(tx?.account_id||a)}</select>`,true,'Puede ser de otra área. La cuenta y la actividad son campos independientes.')}${field('Concepto',`<input name="description" value="${esc(tx?.description||'')}" maxlength="200" required>`,true)}${field('Categoría',`<div class="action-row"><select name="category_id" id="entry-category">${categoryOptions(a,k,tx?.category_id)}</select>${button('＋ Categoría','quick-category','compact')}</div>`,true)}${field('Destinatario (solo reparto externo)',`<select name="person_id"><option value="">Sin destinatario</option>${opts(p,tx?.person_id)}</select>`,true)}${field('Notas',`<textarea name="notes">${esc(tx?.notes||'')}</textarea>`,true)}</div><label class="checkbox"><input name="refund" type="checkbox" ${tx?.kind==='expense'&&tx.amount>0?'checked':''}>Es una devolución de gasto (entrada de dinero)</label><div class="inline-note">Para pagarte a ti desde Academia/Baile, utiliza «Pago interno». Para liquidar al profesor de una asignatura externa ya calculada, utiliza Liquidaciones.</div>`;
 openDialog(tx?'Editar movimiento':'Nuevo movimiento',body,'transaction',tx?`data-id="${tx.id}"`:'');
}
function moveDialog(ids){
 const linked=ids?.length===2;
 const body=(linked?'<p>Se convertirán las dos filas seleccionadas en un único pago vinculado. Sus importes deben ser opuestos y su fecha de operación igual.</p>':`<div class="form-grid">${field('Fecha',`<input name="date" type="date" value="${U.month}-21" required>`)}${field('Importe (€)','<input name="value" inputmode="decimal" required placeholder="0,00">')}${field('Cuenta de origen',`<select name="from_account">${accountOptions(U.area==='baile'?'baile':'academia')}</select>`)}${field('Cuenta de destino',`<select name="to_account">${accountOptions('personal')}</select>`)}${field('Concepto','<input name="description" placeholder="Pago de academia a Personal" required>',true)}</div>`)+field('Tratamiento del pago',`<select name="kind"><option value="distribution">Reparto de resultado hacia mí</option><option value="transfer">Traspaso entre cuentas</option><option value="funding">Aportación de fondos</option><option value="reimbursement">Reembolso de un gasto ya registrado</option></select>`,true)+`<div class="inline-note"><strong>Reparto:</strong> registra lo que te envías desde Academia o Baile a Personal. Tu parte ya se calcula en Actividad; recibir ese dinero en otra cuenta no añade otro ingreso.<br><strong>Aportación, traspaso o reembolso:</strong> mueven saldos sin alterar el resultado. Registra antes el ingreso o gasto original en su área.</div>`;
 openDialog(linked?'Vincular movimientos importados':'Registrar un pago interno',body,linked?'link':'move',linked?`data-ids="${ids.join(',')}"`:'');
}
function accountDialog(a){
 openDialog(a?'Configurar cuenta':'Nueva cuenta',`<div class="form-grid">${field('Nombre',`<input name="name" value="${esc(a?.name||'')}" required>`)}${field('Titular / área',`<select name="area">${areaOptions(a?.area||(U.area==='all'?'personal':U.area))}</select>`)}${field('Saldo inicial (€)',`<input name="opening" value="${number(a?.opening)}" required>`)}${field('Fecha del saldo inicial',`<input name="opening_date" type="date" value="${a?.opening_date==='2000-01-01'?U.month+'-01':a?.opening_date||U.month+'-01'}" required>`)}</div><div class="inline-note">El saldo inicial es el disponible al comenzar ese día, antes de cualquier movimiento importado de esa fecha. No se registra como un ingreso.</div>`,'account',a?`data-id="${a.id}"`:'');
}
function categoryDialog(){
 openDialog('Nueva categoría',`<div class="form-grid">${field('Área',`<select name="area">${areaOptions(U.area==='all'?'personal':U.area)}</select>`)}${field('Tipo','<select name="kind"><option value="expense">Gasto</option><option value="income">Ingreso</option></select>')}${field('Nombre','<input name="name" required maxlength="80">',true)}</div>`,'category');
}
function ruleDialog(){
 const a=U.area==='all'?'personal':U.area;
 openDialog('Nueva regla para importaciones',`<div class="form-grid">${field('Área',`<select name="area" id="rule-area">${areaOptions(a)}</select>`)}${field('El concepto contiene','<input name="term" placeholder="MERCADONA" required>')}${field('Asignar categoría',`<select name="category_id" id="rule-category">${opts(U.data.categories.filter(c=>c.area===a),null)}</select>`,true)}</div>`,'rule');
}

function bindContent(){
 if(U.page==='transactions'){fillTransactions();$('#tx-search').addEventListener('input',fillTransactions);$('#tx-kind').addEventListener('change',fillTransactions);}
 if(U.page==='import'&&U.csv){
  const read=U.csv.readOptions||U.csv;
  $('#csv-skip').value=read.skip;
  $('#csv-delimiter').value=read.delimiter==='\t'?'tab':read.delimiter;
  $('#csv-encoding').value=read.encoding||'utf-8';
  $('[data-action="preview-csv"]').disabled=Boolean(U.csv.needsRead);
  const p=U.csv.config;
  if(p){
   for(const [key,value] of Object.entries(p.mapping))$(`#map-${key}`).value=value;
   $('#csv-account').value=p.account_id;$('#csv-area').value=p.area;
   $('#csv-date-format').value=p.date_format;$('#csv-flip').checked=p.flip;
  }
 }
 if(U.page==='import'&&U.preview){fillImportRows();updateImportCount();}
}
function updateImportCount(){if($('#import-count'))$('#import-count').textContent=`${U.preview.rows.filter(r=>r.selected&&!r.error).length} seleccionados`;}
function csvSettings(){return {text:U.csv.text,skip:U.csv.skip,delimiter:U.csv.delimiter};}

document.addEventListener('click',async e=>{
 const area=e.target.closest('[data-area]');
 if(area?.classList.contains('side-button')){U.area=area.dataset.area;U.selected.clear();render();return;}
 const nav=e.target.closest('[data-page]');if(nav){U.page=nav.dataset.page;U.selected.clear();render();return;}
 const b=e.target.closest('[data-action]');if(!b)return;
 const act=b.dataset.action;
 try{
  if(await B.action(act,b))return;
  if(act==='close-modal')return $('#modal').close();
  if(act==='new-tx')return entryDialog();
  if(act==='edit-tx')return entryDialog(U.data.transactions.find(t=>t.id===b.dataset.id));
  if(act==='new-move')return moveDialog();
  if(act==='new-account')return accountDialog();
  if(act==='edit-account')return accountDialog(U.data.accounts.find(a=>a.id===b.dataset.id));
  if(act==='new-category')return categoryDialog();
  if(act==='new-rule')return ruleDialog();
  if(act==='new-person')return openDialog('Añadir socio o destinatario',field('Nombre','<input name="name" required maxlength="80">',true),'person');
  if(act==='goto-import'){U.page='import';render();return;}
  if(act==='goto-transactions'){U.page='transactions';render();return;}
  if(act==='demo'){U.mode='demo';U.csv=null;U.preview=null;localStorage.setItem(modeKey,'demo');await load();return;}
  if(['backup','export','daily-backup','before-restore'].includes(act)){await downloadFile(`/api/${act}?mode=${U.mode}`);return;}
  if(act==='restore'&&browserMode){
   const file=$('#restore-file')?.files[0];
   if(!file)throw new Error('Elige primero un archivo de respaldo.');
   if(!confirm(`Se sustituirán ${U.mode==='real'?'tus cuentas':'los datos de ejemplo'} de este navegador por el respaldo. ¿Continuar?`))return;
   b.disabled=true;
   try{await globalThis.misCuentasBrowser.restore(file,U.mode);U.selected.clear();U.csv=null;U.preview=null;await load();toast('Respaldo restaurado');}
   finally{b.disabled=false;}
   return;
  }
  if(act==='delete-tx'){
   const t=U.data.transactions.find(x=>x.id===b.dataset.id);
   if(confirm(t.link_id?'Se anularán las dos mitades del pago. ¿Continuar?':'¿Anular este movimiento? Se conserva en el historial del respaldo.')){U.selected.delete(t.id);await mutate('/api/delete',{id:t.id},'Movimiento anulado');}return;
  }
  if(act==='delete-rule'){await mutate('/api/remove-rule',{id:b.dataset.id},'Regla eliminada');return;}
  if(act==='link-selected'){if(U.selected.size!==2)throw Error('Selecciona exactamente dos movimientos de cuentas distintas.');return moveDialog([...U.selected]);}
  if(act==='quick-category'){
   const name=prompt('Nombre de la nueva categoría:');if(!name?.trim())return;
   const a=$('#entry-area').value,k=$('#entry-kind').value;if(!['income','expense'].includes(k))throw Error('Los repartos se clasifican por tipo y destinatario.');
   await api('/api/category',{area:a,kind:k,name});await load();const c=U.data.categories.find(c=>c.area===a&&c.kind===k&&c.name===name.trim());$('#entry-category').innerHTML=categoryOptions(a,k,c?.id);toast('Categoría creada');return;
  }
  if(act==='csv-prev'||act==='csv-next'){U.preview.page=Math.max(0,(U.preview.page||0)+(act==='csv-prev'?-1:1));fillImportRows();return;}
  if(act==='read-csv'){
   const f=$('#csv-file').files[0]||U.csv?.file;if(!f)throw Error('Selecciona un CSV.');if(f.size>8000000)throw Error('El archivo supera 8 MB.');
   const encoding=$('#csv-encoding').value;
   const text=new TextDecoder(encoding).decode(await f.arrayBuffer());const delim=$('#csv-delimiter').value;
   const p={text,skip:Number($('#csv-skip').value),delimiter:delim==='tab'?'\t':delim};
   const r=await api('/api/csv-preview',p);U.csv={...p,...r.result,name:f.name,encoding,file:f};U.preview=null;render();return;
  }
  if(act==='preview-csv'){
   if(U.csv.needsRead)throw Error('Pulsa «Leer columnas» para aplicar los cambios del archivo.');
   const mapping={};for(const id of ['date','description','amount','inflow','outflow','notes','bank_id'])mapping[id]=$(`#map-${id}`).value;
   if(!mapping.date||(!mapping.amount&&!mapping.inflow&&!mapping.outflow))throw Error('Selecciona fecha e importe, o columnas de entrada/salida.');
   const p={...csvSettings(),mapping,account_id:$('#csv-account').value,area:$('#csv-area').value,date_format:$('#csv-date-format').value,flip:$('#csv-flip').checked};
   U.csv.config=p;const r=await api('/api/csv-preview',p);U.preview=r.result;U.preview.rows.forEach(defaultImportActivity);render();$('#preview-panel').scrollIntoView({behavior:'smooth'});return;
  }
  if(act==='confirm-import'){
   const incomplete=U.preview.rows.find(r=>r.selected&&!r.error&&r.activity?.method==='external'&&!r.activity.course_id&&!r.entry_id&&r.treatment!=='bank_only');
   if(incomplete)throw Error('Selecciona la asignatura externa de la fila '+incomplete.row);
   const rows=U.preview.rows.filter(r=>r.selected&&!r.error);if(!rows.length)throw Error('No hay filas seleccionadas.');
   const duplicates=rows.filter(r=>r.duplicate).length;
   if(duplicates&&!confirm(`Has seleccionado ${duplicates} posibles duplicados. ¿Importarlos igualmente?`))return;
   b.disabled=true;const r=await api('/api/import',{name:U.csv.name,rows});U.csv=null;U.preview=null;U.selected.clear();await load();toast(`${r.result.count} movimientos importados`);return;
  }
  if(act==='undo-import'){if(confirm('¿Anular los movimientos de esta importación? No afecta a registros manuales.'))await mutate('/api/undo-import',{id:b.dataset.id},'Importación anulada');return;}
 }catch(err){reportError(err);b.disabled=false;}
});

document.addEventListener('input',e=>{if(e.target.closest('[data-form="entry"]'))B.updateEntryPreview();});
document.addEventListener('change',e=>{
 B.change(e);
 if(U.csv&&e.target.matches('#csv-file,#csv-encoding,#csv-skip,#csv-delimiter')){
  U.csv.needsRead=true;U.preview=null;$('#preview-panel')?.remove();
  const delimiter=$('#csv-delimiter').value;
  U.csv.readOptions={skip:Number($('#csv-skip').value),delimiter:delimiter==='tab'?'\t':delimiter,encoding:$('#csv-encoding').value};
  $('[data-action="preview-csv"]').disabled=true;
  toast('Pulsa «Leer columnas» para aplicar estos cambios.');
 }
 if(U.csv&&e.target.matches('[id^="map-"],#csv-account,#csv-area,#csv-date-format,#csv-flip')){
  const mapping={};for(const id of ['date','description','amount','inflow','outflow','notes','bank_id'])mapping[id]=$(`#map-${id}`).value;
  U.csv.config={...csvSettings(),mapping,account_id:$('#csv-account').value,area:$('#csv-area').value,date_format:$('#csv-date-format').value,flip:$('#csv-flip').checked};
  U.preview=null;$('#preview-panel')?.remove();
 }
 if(e.target.matches('[data-select-tx]')){e.target.checked?U.selected.add(e.target.dataset.selectTx):U.selected.delete(e.target.dataset.selectTx);fillTransactions();}
 if(e.target.matches('[data-import-row]')){U.preview.rows[Number(e.target.dataset.importRow)].selected=e.target.checked;updateImportCount();}
 if(e.target.matches('[data-csv-field]'))updateImportRow(e.target);
 if(e.target.id==='entry-area'||e.target.id==='entry-kind'){
  $('#entry-category').innerHTML=categoryOptions($('#entry-area').value,$('#entry-kind').value,null);
  if(e.target.id==='entry-area')$('#entry-account').value=U.data.accounts.find(a=>a.area===e.target.value)?.id||'';
 }
 if(e.target.id==='rule-area')$('#rule-category').innerHTML=opts(U.data.categories.filter(c=>c.area===e.target.value),null);
});
document.addEventListener('submit',async e=>{
 const form=e.target.closest('[data-form]');if(!form)return;e.preventDefault();
 const values=Object.fromEntries(new FormData(form));const btn=$('button[type=submit]',form);btn.disabled=true;const error=$('.error',form);error.textContent='';
 try{
  const name=form.dataset.form;
  B.prepare(name,values,form);
  if(name==='shares'){values.area=form.dataset.area;values.month=U.month;values.shares=$$('[data-person]',form).map(i=>({person_id:i.dataset.person,percent:i.value||'0'}));}
  if(name==='transaction'){values.refund=Boolean($('[name=refund]',form)?.checked);if(values.kind!=='distribution')values.person_id='';}
  if(form.dataset.id)values.id=form.dataset.id;
  if(name==='link')values.ids=form.dataset.ids.split(',');
  if(name==='ai'){
   btn.textContent='Consultando al modelo local…';
   const response=await api('/api/ai',{...values,month:U.month});$('#ai-answer').textContent=response.result;$('#ai-answer').hidden=false;
  }else{
   await api(`/api/${name}`,values);if(name==='entry')U.month=values.period;if($('#modal').open)$('#modal').close();if(name==='link')U.selected.clear();await load();toast('Guardado');
  }
 }catch(err){reportError(err,form);}finally{btn.disabled=false;if(form.dataset.form==='ai')btn.textContent='Consultar en mi Mac';}
});
$('#new-tx').addEventListener('click',()=>B.entryDialog());
$('#mode').addEventListener('change',async e=>{U.mode=e.target.value;localStorage.setItem(modeKey,U.mode);U.csv=null;U.preview=null;U.selected.clear();try{await load();}catch(err){reportError(err);}});
$('#month').addEventListener('change',async e=>{if(!/^\d{4}-\d{2}$/.test(e.target.value))return;U.month=e.target.value;U.selected.clear();try{await load();}catch(err){reportError(err);}});
async function init(){try{const session=await api('/api/session');U.csrf=session.csrf;await load();}catch(err){$('#content').textContent=err.message;}}
init();
