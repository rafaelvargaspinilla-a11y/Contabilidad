import {downloadFile} from './transport.mjs';

export function businessUI(h) {
 const {U,$,$$,esc,euro,number,field,button,head,stat,areaOptions,accountOptions,categoryOptions,opts,openDialog,api,load,render,toast}=h;
 const names={academia:'Academia',baile:'Baile',personal:'Personal'};
 const F=()=>U.data.finance;
 const getEntry=id=>F().entries.find(e=>e.id===id);
 const day=()=>U.month+'-15';
 const y=()=>Number(U.month.slice(0,4))-(Number(U.month.slice(5))<9?1:0);
 let courseYear=null,semester=Number(U.month.slice(5))<=5?2:1;
 const selected=()=>F().entries.filter(e=>e.period===U.month&&(U.area==='all'||e.area===U.area));
 const tr=items=>items.map(x=>`<td>${x}</td>`).join('');
 function summary(){
  const s=F().summary[U.area];
  let html=head(U.area==='all'?'Lo que te corresponde, de verdad.':names[U.area]+', con tu parte clara.','Resultado por mes de actividad. Los cobros y los saldos bancarios se consultan por separado.',button('Añadir actividad','new-entry','primary'));
  if(!F().entries.length)html+=`<div class="inline-note">Empieza por configurar las asignaturas, importar un extracto o ${button('Explorar ejemplo','demo')}.</div>`;
  if(s.review)html+=`<div class="inline-note warning">Hay ${s.review} registros anteriores pendientes de confirmar su reparto. Se conservan en el banco; aún no se incluyen en tu resultado. Revísalos desde Actividad.</div>`;
  html+=`<div class="summary-grid">${stat('Tu parte de ingresos',s.my_income,'Después de descontar la parte del profesorado')}${stat('Tu parte de gastos',s.my_expense,'Según el porcentaje guardado en cada registro')}${stat('Retenciones en tus facturas',s.withholding,'Importes retenidos, separados de los gastos')}${stat('Tu resultado tras retenciones',s.my_available,'Ingresos atribuidos − gastos atribuidos − retenciones',true)}</div>`;
  html+=`<div class="inline-note">Este resultado incluye actividad pendiente de cobrar o pagar. No es tu saldo bancario ni el beneficio fiscal definitivo. Las liquidaciones y los traspasos no vuelven a contarse como ingresos o gastos.</div>`;
  const expenses={};selected().filter(e=>e.kind==='expense'&&!e.review).forEach(e=>{const name=e.category||'Sin categoría';expenses[name]=(expenses[name]||0)+e.my_expense;});
  const bars=Object.entries(expenses).sort((a,b)=>b[1]-a[1]),max=Math.max(1,...bars.map(([,v])=>v));
  html+=`<div class="panel"><h2>Tu gasto por categoría</h2>${bars.map(([name,v])=>`<div class="bar-row"><span>${esc(name)}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(0,v)/max*100}%"></div></div><strong class="num">${euro(v)}</strong></div>`).join('')||'<p>Sin gastos en este periodo.</p>'}</div>`;
  html+=`<div class="panel"><h2>El detalle del mes</h2><div class="table-wrap"><table><thead><tr><th>ÁREA</th><th class="num">INGRESOS BRUTOS</th><th class="num">PARTE PROFESORADO</th><th class="num">GASTOS TOTALES</th><th class="num">TU RESULTADO TRAS RETENCIONES</th></tr></thead><tbody>${Object.entries(names).filter(([a])=>U.area==='all'||a===U.area).map(([a,n])=>{const r=F().summary[a];return `<tr>${tr([n,euro(r.income),euro(r.teacher),euro(r.expense),'<strong>'+euro(r.my_available)+'</strong>'])}</tr>`;}).join('')}</tbody></table></div></div>`;
  html+=`<div class="split-grid"><div class="panel"><h2>Cobros y pagos pendientes del mes</h2><div class="receipt-card"><span>Por cobrar</span><strong>${euro(selected().filter(e=>e.kind==='income').reduce((n,e)=>n+e.pending,0))}</strong></div><div class="receipt-card"><span>Por pagar</span><strong>${euro(selected().filter(e=>e.kind==='expense').reduce((n,e)=>n+e.pending,0))}</strong></div><p class="small">Situación actual de los registros de este mes; incluye la parte de otras personas cuando corresponda.</p>${button('Ver actividad','goto-activity')}</div><div class="panel"><h2>Saldo de reparto con socio / pareja</h2>${Object.entries(F().balances).filter(([a])=>U.area==='all'||U.area===a).map(([a,b])=>`<div class="receipt-card"><span>${names[a]}<br><small>${b>=0?'Pendiente de recibir':'Pendiente de entregar'}</small></span><strong>${euro(Math.abs(b))}</strong></div>`).join('')}<p class="small">Acumulado hasta el cierre del mes, según quién cobró o pagó y las liquidaciones registradas. La parte del profesorado se liquida aparte.</p>${button('Ver liquidaciones','goto-settlements')}</div></div>`;
  html+=`<div class="panel"><h2>Tus cuentas bancarias</h2><div class="account-grid">${U.data.accounts.filter(a=>U.area==='all'||a.area===U.area).map(a=>{const balance=(a.opening_date<=U.month+'-31'?a.opening:0)+U.data.transactions.filter(t=>t.account_id===a.id&&t.date<=U.month+'-31').reduce((v,t)=>v+t.amount,0);return `<div><div class="sub">${esc(a.name)}</div><strong class="account-balance">${euro(balance)}</strong></div>`;}).join('')}</div><div class="action-row">${button('Exportar actividad','export-activity')}${button('Descargar respaldo','backup')}</div></div>`;
  if(U.area==='all'||U.area==='personal'){
   const receipts=U.data.transactions.filter(t=>t.area==='personal'&&t.amount>0&&t.link_id&&t.date.startsWith(U.month)&&['distribution','remuneration'].includes(t.kind));
   html+=`<div class="panel"><h2>Dinero recibido en Personal</h2>${['academia','baile'].map(a=>{const amount=receipts.filter(t=>U.data.transactions.some(other=>other.link_id===t.link_id&&other.area===a&&other.amount<0)).reduce((n,t)=>n+t.amount,0);return `<div class="receipt-card"><span>Desde ${names[a]}</span><strong>${euro(amount)}</strong></div>`;}).join('')}<p class="small">Pagos internos efectivamente registrados en este mes. Tu resultado ya incluye la parte que te corresponde en cada actividad: recibirla en otra cuenta no vuelve a generar ingresos.</p>${button('Registrar pago interno','new-move')}</div>`;
  }
  return html;
 }
 function activity(){
  const rows=selected();
  return head('Ingresos, gastos y lo que te corresponde.','Cada registro conserva su bruto, retención y porcentajes. El banco se vincula sin duplicar la actividad.',button('Nuevo registro','new-entry','primary')+button('Exportar actividad','export-activity'))+
   `<div class="panel"><div class="sub">${rows.length} registros en ${U.month}. ${rows.filter(e=>e.review).length} por revisar.</div><div class="table-wrap"><table><thead><tr><th>CONCEPTO</th><th>ÁREA / TIPO</th><th class="num">BRUTO / TOTAL</th><th>REPARTO</th><th class="num">TU RESULTADO</th><th>COBRO / PAGO</th><th></th></tr></thead><tbody>${rows.map(e=>`<tr>${tr([`<strong>${esc(e.description)}</strong><div class="sub">${e.date}${e.course?' · '+esc(e.course):''}${e.review?' · REVISAR REPARTO':''}</div>`,`${names[e.area]}<div class="sub">${e.kind==='income'?'Ingreso':e.refund?'Devolución':'Gasto'}</div>`,euro(e.gross),`Tú: ${e.my_bps/100} %${e.teacher_bps?`<div class="sub">Profesor: ${e.teacher_bps/100} % · Academia: ${100-e.teacher_bps/100} %</div>`:''}${e.withholding?`<div class="sub">IRPF: ${e.tax_bps/100} % · ${euro(e.withholding)}</div>`:''}`,`<strong>${e.review?'Por revisar':euro(e.my_available)}</strong>`,`<div>${e.holder==='me'?'Por ti':'Por socio/pareja'}</div><div class="sub">Registrado: ${euro(e.paid)}<br>Pendiente: ${euro(e.pending)}</div>`,`${button('Editar','edit-entry','compact',`data-id="${e.id}"`)} ${e.pending?button(e.kind==='income'?'Cobrar':'Pagar','entry-cash','compact',`data-id="${e.id}"`):''} ${button('Anular','void-entry','quiet compact danger',`data-id="${e.id}"`)}`])}</tr>`).join('')||'<tr><td colspan="7">Todavía no hay actividad en este periodo.</td></tr>'}</tbody></table></div></div>`;
 }
 function courses(){
  const year=courseYear??y();const months=semester===1?[9,10,11,12].map(m=>year+'-'+m.toString().padStart(2,'0')):[1,2,3,4,5].map(m=>(year+1)+'-'+m.toString().padStart(2,'0'));
  const list=F().courses.filter(c=>c.year===year&&c.semester===semester);
  return head('Asignaturas, mes a mes.','Pulsa una celda para introducir o editar el ingreso mensual. Cada asignatura pertenece a un curso académico y cuatrimestre.',button('Nueva asignatura','new-course','primary'))+
   `<div class="filters"><label>Curso académico <input id="course-year" type="number" min="2000" max="2200" value="${year}" aria-label="Año de inicio del curso"></label><span>– ${year+1}</span><select id="course-semester" aria-label="Cuatrimestre"><option value="1" ${semester===1?'selected':''}>Septiembre–diciembre</option><option value="2" ${semester===2?'selected':''}>Enero–mayo</option></select></div><div class="panel"><div class="table-wrap"><table><thead><tr><th>ASIGNATURA</th>${months.map(m=>`<th class="num">${m}</th>`).join('')}<th class="num">TOTAL BRUTO</th><th class="num">TU PARTE TRAS RETENCIÓN</th></tr></thead><tbody>${list.map(c=>{const all=F().entries.filter(e=>e.course_id===c.id&&!e.review);return `<tr><td><strong>${esc(c.name)}</strong><div class="sub">${c.ownership==='own'?'Propia · 100 % para ti':`Externa · ${esc(c.teacher)}<br>Profesor ${c.teacher_bps/100} % / Academia ${100-c.teacher_bps/100} %`}</div>${button('Configurar','edit-course','quiet compact',`data-id="${c.id}"`)}</td>${months.map(m=>{const entries=all.filter(e=>e.period===m);return `<td class="num">${button(entries.length?euro(entries.reduce((n,e)=>n+e.gross,0)):'＋ Ingreso','course-month','compact',`data-course="${c.id}" data-month="${m}"`)}${entries.length?`<div class="sub">Para ti: ${euro(entries.reduce((n,e)=>n+e.my_available,0))}</div>`:''}</td>`;}).join('')}<td class="num">${euro(all.reduce((n,e)=>n+e.gross,0))}</td><td class="num"><strong>${euro(all.reduce((n,e)=>n+e.my_available,0))}</strong></td></tr>`;}).join('')||`<tr><td colspan="${months.length+3}">Crea las asignaturas de este cuatrimestre. El siguiente puede tener otras distintas.</td></tr>`}</tbody></table></div><p class="small">La parte de gastos generales se muestra en el resumen de Academia, sin descontarla de nuevo a cada asignatura.</p></div>`;
 }
 function preferences(){const p=F().preferences;return `<div class="panel"><h2>Porcentajes para nuevos registros</h2><p>Los cambios se aplican al crear nuevos registros. Los anteriores mantienen sus porcentajes y se pueden corregir individualmente.</p><form data-form="preferences"><div class="form-grid">${field('Tu parte de gastos y margen de Academia (%)',`<input name="my_share" type="number" min="0" max="100" step="0.01" value="${p.my_share/100}" required>`)}${field('IRPF de tus facturas propias (%)',`<input name="tax" type="number" min="0" max="99.99" step="0.01" value="${p.tax/100}" required>`)}${field('Parte del profesor externo por defecto (%)',`<input name="teacher_share" type="number" min="0" max="100" step="0.01" value="${p.teacher_share/100}" required>`,false,'Cada asignatura puede tener su propio porcentaje. La parte de Academia es el resto.')}</div><div class="error"></div><div class="form-actions"><button class="button primary" type="submit">Guardar valores iniciales</button></div></form></div>`;}
 function settlements(){
  const rows=F().settlements.filter(s=>s.date.startsWith(U.month)&&(U.area==='all'||s.area===U.area));
  return head('Liquidar lo que ya está repartido.','Estos pagos ajustan los saldos pendientes entre personas y el banco, sin añadir otro gasto o ingreso.',button('Nueva liquidación','new-settlement','primary'))+
   `<div class="summary-grid">${Object.entries(F().balances).map(([a,b])=>stat(names[a],Math.abs(b),b>=0?'Pendiente de recibir, acumulado al cierre':'Pendiente de entregar, acumulado al cierre')).join('')}</div><div class="panel"><h2>Liquidaciones de ${U.month}</h2><div class="table-wrap"><table><thead><tr><th>FECHA</th><th>ÁREA</th><th>CONCEPTO</th><th>IMPORTE</th><th></th></tr></thead><tbody>${rows.map(s=>`<tr>${tr([s.date,names[s.area],s.role==='teacher'?'Pago al profesorado · '+esc(getEntry(s.entry_id)?.description||''):s.direction==='to_partner'?'Entregado a socio/pareja':'Recibido de socio/pareja',euro(s.amount),button('Anular','void-settlement','quiet compact danger',`data-id="${s.id}"`)])}</tr>`).join('')||'<tr><td colspan="5">No hay liquidaciones este mes.</td></tr>'}</tbody></table></div></div><div class="panel"><h2>Partes del profesorado por liquidar</h2><div class="table-wrap"><table><thead><tr><th>ASIGNATURA / MES</th><th>CALCULADO</th><th>PAGADO</th><th>PENDIENTE</th></tr></thead><tbody>${F().entries.filter(e=>e.method==='external'&&!e.review&&e.period<=U.month).map(e=>{const paid=F().settlements.filter(s=>s.entry_id===e.id&&s.date<=U.month+'-31').reduce((n,s)=>n+s.amount,0);return `<tr>${tr([esc(e.description)+' · '+e.period,euro(e.teacher),euro(paid),euro(e.teacher-paid)])}</tr>`;}).join('')||'<tr><td colspan="4">Sin asignaturas externas registradas.</td></tr>'}</tbody></table></div></div>`;
 }
 function entryDialog(entry=null,defaults={}){
  const e=entry||{};const area=e.area||defaults.area||(U.area==='all'?'personal':U.area),kind=e.kind||defaults.kind||'expense';
  const body=`<div class="form-grid">${field('Área',`<select id="act-area" name="area">${areaOptions(area)}</select>`)}${field('Tipo',`<select id="act-kind" name="kind"><option value="income" ${kind==='income'?'selected':''}>Ingreso</option><option value="expense" ${kind==='expense'?'selected':''}>Gasto / devolución</option></select>`)}${field('Mes de actividad',`<input id="act-period" name="period" type="month" value="${e.period||defaults.period||U.month}" required>`)}${field('Fecha del registro',`<input name="date" type="date" value="${e.date||(defaults.period||U.month)+'-15'}" required>`)}${field('Tratamiento / reparto','<select id="act-method" name="method"></select>')}${field('Asignatura (Academia)','<select id="act-course" name="course_id"><option value="">Sin asignatura</option></select>')}${field('Concepto',`<input name="description" maxlength="200" value="${esc(e.description||'')}" placeholder="Opcional si has elegido asignatura">`,true)}${field('Categoría','<select id="act-category" name="category_id"></select>',true)}${field('Ingreso bruto / gasto total (€)',`<input id="act-gross" name="gross_value" inputmode="decimal" value="${e.id?number(e.gross):''}" required>`)}${field('Tu porcentaje (%)',`<input id="act-share" name="my_percent" type="number" min="0" max="100" step="0.01">`)}${field('Porcentaje del profesor (%)','<input id="act-teacher" name="teacher_percent" type="number" min="0" max="100" step="0.01">')}${field('Retención IRPF (%)','<input id="act-tax" name="tax_percent" type="number" min="0" max="99.99" step="0.01">')}${field('Quién cobra o paga',`<select name="holder"><option value="me" ${e.holder!=='partner'?'selected':''}>Yo / cuenta que gestiono</option><option value="partner" ${e.holder==='partner'?'selected':''}>Socio / pareja</option></select>`)}${field('Estado inicial',`<select name="cash_status" ${e.id?'disabled':''}><option value="pending">Pendiente de cobrar / pagar</option><option value="paid">Ya cobrado / pagado completo</option></select>`)}${!e.id?field('Cuenta si has cobrado/pagado tú',`<select name="account_id">${accountOptions(area)}</select>`,true):''}${field('Notas',`<textarea name="notes">${esc(e.notes||'')}</textarea>`,true)}</div><label class="checkbox"><input name="refund" type="checkbox" ${e.refund?'checked':''}>Devolución de un gasto (reduce el gasto)</label><div id="entry-preview" class="inline-note" aria-live="polite"></div><div class="inline-note">Si el cobro ya está importado, guarda el registro como pendiente y concílialo desde Banco. Si marcas «Ya cobrado» se añadirá un movimiento bancario cuando el cobro sea tuyo.</div>${e.id?`<div class="sub">Registrado: ${euro(e.paid)} · Pendiente: ${euro(e.pending)}. Editar el bruto o el IRPF no cambia el importe real del extracto.</div><div class="action-row">${F().links.filter(l=>l.entry_id===e.id).map(l=>button('Desvincular '+euro(l.amount),'unlink-entry','quiet compact',`data-entry="${e.id}" data-tx="${l.tx_id}"`)).join('')}${e.external_paid?button('Desmarcar cobro de socio/pareja','external-unpaid','quiet compact',`data-id="${e.id}"`):''}</div>`:''}`;
  openDialog(e.id?'Editar actividad':'Nueva actividad',body,'entry',e.id?`data-id="${e.id}"`:'');
  refreshEntry({method:e.method,course_id:e.course_id||defaults.course_id,my_bps:e.my_bps,tax_bps:e.tax_bps,teacher_bps:e.teacher_bps,category_id:e.category_id});
 }
 function refreshEntry(seed={}){
  const area=$('#act-area').value,kind=$('#act-kind').value;
  const methods=area==='academia'&&kind==='income'?[['own','Propia · 100 % para mí'],['external','Externa · reparto profesor/academia']]:area==='personal'?[['individual','Individual · 100 % para mí']]:[['individual','Individual · 100 % para mí'],['shared',area==='academia'?'General compartido · porcentaje configurado':'Compartido · 50 % por defecto']];
  const course=F().courses.find(c=>c.id===seed.course_id);
  const method=course?.ownership||seed.method||(area==='academia'&&kind==='expense'?'shared':methods[0][0]);
  $('#act-method').innerHTML=methods.map(([id,n])=>`<option value="${id}" ${id===method?'selected':''}>${n}</option>`).join('');
  const m=$('#act-method').value,period=$('#act-period').value;
  const list=F().courses.filter(c=>c.ownership===m&&(c.semester===1?period>=c.year+'-09'&&period<=c.year+'-12':period>=(c.year+1)+'-01'&&period<=(c.year+1)+'-05'));
  $('#act-course').disabled=area!=='academia'||kind!=='income';
  $('#act-course').innerHTML='<option value="">Sin asignatura</option>'+opts(list,seed.course_id);
  $('#act-category').innerHTML=categoryOptions(area,kind,seed.category_id);
  $('#act-share').value=(seed.my_bps??(m==='shared'||m==='external'?(area==='academia'?F().preferences.my_share:5000):10000))/100;
  $('#act-share').disabled=!['shared','external'].includes(m);
  $('#act-teacher').value=(seed.teacher_bps??course?.teacher_bps??F().preferences.teacher_share)/100;
  $('#act-teacher').disabled=m!=='external';
  $('#act-tax').value=(seed.tax_bps??(area==='academia'&&kind==='income'&&m==='own'?F().preferences.tax:0))/100;
  $('#act-tax').disabled=kind!=='income'||['shared','external'].includes(m);
  updateEntryPreview();
 }
 function moneyInput(v){const s=String(v).trim().replace(/\s|€/g,'');return Math.round(Number(s.includes(',')?s.replace(/\./g,'').replace(',','.'):s)*100)||0;}
 function updateEntryPreview(){
  if(!$('#act-gross'))return;
  const gross=moneyInput($('#act-gross').value),method=$('#act-method').value,kind=$('#act-kind').value;
  const teacher=method==='external'?Math.round(gross*Number($('#act-teacher').value)/100):0;
  const mine=Math.round((gross-teacher)*(['shared','external'].includes(method)?Number($('#act-share').value):100)/100);
  const tax=kind==='income'&&!$('#act-tax').disabled?Math.round(gross*Number($('#act-tax').value)/100):0;
  $('#entry-preview').textContent=kind==='income'?`Profesor: ${euro(teacher)} · Tu parte antes de retención: ${euro(mine)} · IRPF: ${euro(tax)} · Tu parte tras retención: ${euro(mine-tax)} · Líquido total a cobrar: ${euro(gross-tax)}`:`Tu parte del gasto: ${euro(mine)} · Parte de la otra persona: ${euro(gross-mine)}`;
 }
 function courseDialog(c){openDialog(c?'Configurar asignatura':'Nueva asignatura',`<div class="form-grid">${field('Nombre',`<input name="name" value="${esc(c?.name||'')}" required>`,true)}${field('Año inicial del curso académico',`<input name="year" type="number" min="2000" max="2200" value="${c?.year??courseYear??y()}" required>`)}${field('Cuatrimestre',`<select name="semester"><option value="1" ${(c?.semester??semester)!==2?'selected':''}>Septiembre–diciembre</option><option value="2" ${(c?.semester??semester)===2?'selected':''}>Enero–mayo</option></select>`)}${field('Quién imparte la asignatura',`<select name="ownership"><option value="own" ${c?.ownership!=='external'?'selected':''}>Yo · ingreso propio</option><option value="external" ${c?.ownership==='external'?'selected':''}>Profesor externo</option></select>`)}${field('Nombre del profesor externo',`<input name="teacher" value="${esc(c?.teacher||'')}">`)}${field('Parte del profesor externo (%)',`<input name="teacher_percent" type="number" min="0" max="100" step="0.01" value="${(c?.teacher_bps??F().preferences.teacher_share)/100}">`,true,'La academia conserva el resto. Este porcentaje se copia al crear cada ingreso y queda guardado en él.')}</div>`,'course',c?`data-id="${c.id}"`:'');}
 function cashDialog(e){openDialog(e.kind==='income'?'Registrar cobro':'Registrar pago',`<p>${esc(e.description)} · pendiente ${euro(e.pending)}</p><div class="form-grid">${field('Fecha del cobro/pago',`<input name="cash_date" type="date" value="${day()}" required>`)}${field('Importe (€)',`<input name="cash_value" inputmode="decimal" value="${number(e.pending)}" required>`)}${field('Cuenta (si cobras/pagas tú)',`<select name="account_id">${accountOptions(e.area)}</select>`,true)}</div><div class="inline-note">${e.holder==='partner'?'Se marcará como cobrado/pagado por socio o pareja, sin mover tus cuentas bancarias.':'Se añadirá un movimiento a esa cuenta. Si ya lo importaste, utiliza Conciliar desde Banco.'}</div>`,'cash',`data-id="${e.id}"`);}
 function reconcileDialog(t){
  const candidates=F().entries.filter(e=>e.holder==='me'&&e.pending>0&&(e.kind==='income'||e.refund?t.amount>0:t.amount<0));
  const links=F().links.filter(l=>l.tx_id===t.id);const automatic=links.length&&links.every(l=>getEntry(l.entry_id)?.source==='bank');
  const available=Math.abs(t.amount)-(automatic?0:links.reduce((n,l)=>n+l.amount,0));
  openDialog('Conciliar con actividad existente',`<p>${esc(t.description)} · ${euro(t.amount)} · disponible ${euro(available)}</p><input type="hidden" name="tx_id" value="${t.id}"><input type="hidden" name="replace_automatic" value="${automatic?'1':''}"><p class="small">Introduce cuánto de este movimiento corresponde a cada registro. Puedes repartir un único cobro entre varias asignaturas. ${automatic?'Se sustituirá el registro automático del banco para no duplicar ingresos/gastos.':''}</p><div class="allocation-list">${candidates.map(e=>field(`${esc(e.description)} · ${e.period} · pendiente ${euro(e.pending)}`,`<input data-allocation="${e.id}" inputmode="decimal" placeholder="0,00" aria-label="Asignar a ${esc(e.description)}">`)).join('')||'<p>No hay registros pendientes compatibles. Crea primero la actividad con estado pendiente.</p>'}</div>`,'reconcile');
 }
 function settlementDialog(){
  const area=U.area==='baile'?'baile':'academia';
  openDialog('Liquidación de reparto o profesorado',`<div class="form-grid">${field('Área',`<select name="area"><option value="academia" ${area==='academia'?'selected':''}>Academia</option><option value="baile" ${area==='baile'?'selected':''}>Baile</option></select>`)}${field('Destino','<select name="role"><option value="partner">Socio / pareja</option><option value="teacher">Profesor externo</option></select>')}${field('Sentido (entre socio/pareja)','<select name="direction"><option value="to_partner">Yo entrego dinero</option><option value="from_partner">Yo recibo dinero</option></select>')}${field('Quién paga al profesor','<select name="holder"><option value="me">Yo</option><option value="partner">Mi socio</option></select>')}${field('Ingreso asociado (solo profesorado)',`<select name="entry_id"><option value="">Sin asignatura · liquidación con socio/pareja</option>${F().entries.filter(e=>e.method==='external').map(e=>`<option value="${e.id}">${esc(e.description)} · parte profesor ${euro(e.teacher)}</option>`).join('')}</select>`,true)}${field('Fecha',`<input name="date" type="date" value="${day()}" required>`)}${field('Importe (€)','<input name="value" inputmode="decimal" required>')}${field('Cuenta para un pago/cobro nuevo',`<select name="account_id">${accountOptions(area)}</select>`,true)}${field('O utilizar un movimiento ya importado',`<select name="tx_id"><option value="">Crear movimiento bancario nuevo</option>${U.data.transactions.filter(t=>!t.link_id&&['income','expense'].includes(t.kind)).slice(0,500).map(t=>`<option value="${t.id}">${t.date} · ${esc(t.description)} · ${euro(t.amount)}</option>`).join('')}</select>`,true)}${field('Notas','<textarea name="notes"></textarea>',true)}</div><div class="inline-note">Las partes ya se han calculado en la actividad. Esta liquidación solo mueve dinero. Si eliges un movimiento importado, su clasificación automática se sustituye por la liquidación.</div>`,'settlement');
 }
 async function action(act,b){
  if(act==='new-entry'||act==='new-tx'){entryDialog();return true;}
  if(act==='edit-entry'){entryDialog(getEntry(b.dataset.id));return true;}
  if(act==='entry-cash'){cashDialog(getEntry(b.dataset.id));return true;}
  if(act==='new-course'||act==='edit-course'){courseDialog(F().courses.find(c=>c.id===b.dataset.id));return true;}
  if(act==='new-settlement'){settlementDialog();return true;}
  if(act==='reconcile-bank'){reconcileDialog(U.data.transactions.find(t=>t.id===b.dataset.id));return true;}
  if(act==='classify-bank'){const r=await api('/api/classify-bank',{tx_id:b.dataset.id});await load();entryDialog(getEntry(r.result));return true;}
  if(act==='goto-activity'||act==='goto-settlements'){U.page=act==='goto-activity'?'activity':'settlements';render();return true;}
  if(act==='export-activity'){await downloadFile('/api/export-activity?mode='+U.mode);return true;}
  if(act==='course-month'){
   const rows=F().entries.filter(e=>e.course_id===b.dataset.course&&e.period===b.dataset.month);
   if(rows.length===1)entryDialog(rows[0]);
   else if(!rows.length)entryDialog(null,{area:'academia',kind:'income',course_id:b.dataset.course,period:b.dataset.month});
   else {U.month=b.dataset.month;U.area='academia';U.page='activity';await load();}
   return true;
  }
  if(['void-entry','void-settlement','unlink-entry','external-unpaid'].includes(act)){
   const message=act==='void-entry'?'Anular esta actividad conserva los movimientos bancarios, que quedarán sin asignar. ¿Continuar?':act==='void-settlement'?'Anular esta liquidación también anula su movimiento bancario asociado. ¿Continuar?':'Desvincular el cobro/pago deja la actividad pendiente y conserva el banco. ¿Continuar?';
   if(!confirm(message))return true;
   const route={'void-entry':'delete-entry','void-settlement':'delete-settlement','unlink-entry':'unlink','external-unpaid':'external-unpaid'}[act];
   await api('/api/'+route,{id:b.dataset.id,entry_id:b.dataset.entry,tx_id:b.dataset.tx});
   if($('#modal').open)$('#modal').close();await load();toast('Actualizado');return true;
  }
  return false;
 }
 function change(e){
  const id=e.target.id;
  if(id==='course-year'||id==='course-semester'){courseYear=Number($('#course-year').value);semester=Number($('#course-semester').value);render();}
  if(['act-area','act-kind','act-method','act-course','act-period'].includes(id)){
   const seed={};if(!['act-area','act-kind'].includes(id))seed.method=$('#act-method').value;
   if(!['act-area','act-kind','act-method'].includes(id))seed.course_id=$('#act-course').value;
   refreshEntry(seed);
  }
  if(e.target.closest('[data-form="entry"]'))updateEntryPreview();
 }
 function prepare(name,values,form){
  if(name==='entry')values.refund=Boolean($('[name="refund"]',form)?.checked);
  if(name==='reconcile'){
   values.replace_automatic=values.replace_automatic==='1';
   values.links=$$('[data-allocation]',form).filter(i=>i.value.trim()).map(i=>({entry_id:i.dataset.allocation,value:i.value}));
   if(!values.links.length)throw Error('Asigna un importe a algún registro.');
  }
  return values;
 }
 function bind(){if(U.page==='settings')$('.page-head').insertAdjacentHTML('afterend',preferences());}
 return {summary,activity,courses,settlements,entryDialog,action,change,prepare,bind,updateEntryPreview};
}
