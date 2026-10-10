function allocated(amount, rows){
 let cumulative=0, previous=0;
 return rows.map(r=>{cumulative+=r.bps;const next=Math.round(amount*cumulative/10000), value=next-previous;previous=next;return value;});
}
export function budgetUI({U,$,$$,esc,euro,head,button,api,load,toast}){
 let draft=null, key='';
 const categories=()=>U.data.categories.filter(c=>c.area==='personal'&&c.kind==='expense');
 const actual=id=>U.data.finance.entries.filter(e=>e.area==='personal'&&e.period===U.month&&e.kind==='expense'&&!e.review&&e.category_id===id).reduce((sum,e)=>sum+e.my_expense,0);
 function render(){
  const b=U.data.budget;
  const nextKey=`${U.mode}:${U.month}:${JSON.stringify(b.saved)}`;
  if(key!==nextKey){draft=null;key=nextKey;}
  const rows=b.saved?.allocations.map(r=>({category_id:r.category_id,percent:r.bps/100}))||[];
  if(!draft)draft=rows;
  const amount=b.saved?.amount??b.available;
  return head('Tu presupuesto del mes.','Distribuye los beneficios del mes anterior. Los gastos personales se comparan después con tu presupuesto.')+
   `<div class="panel"><h2>Dinero disponible: ${euro(amount)}</h2><p>Base de ${esc(b.source)}: tus ingresos cobrados después de retenciones (${euro(b.saved?.income??b.received)}) menos tu parte de los gastos de Academia y Baile (${euro(b.saved?.business_expenses??b.business_expenses)}). No se descuentan los gastos de Personal ni se duplican traspasos.</p>${b.legacy_adjusted?'<p class="inline-note">Este presupuesto se creó antes de descontar los gastos de actividad. Hemos ajustado la base manteniendo los porcentajes. Pulsa Guardar presupuesto para fijar la cantidad corregida.</p>':''}${!b.saved&&b.deficit?`<p class="inline-note">Los gastos de actividad superan tus ingresos en ${euro(b.deficit)}. No hay beneficio disponible para repartir.</p>`:''}${b.saved?'<p>La cantidad de partida queda guardada; editar los porcentajes no cambia esa cantidad.</p>':''}<form id="budget-form"><div id="budget-rows"></div><div class="action-row">${button('Añadir categoría','budget-add')}${button('Crear categoría personal','budget-category')}</div><p id="budget-total" aria-live="polite"></p><div class="error"></div><button type="submit" class="button primary">Guardar presupuesto</button></form></div>`+
   (b.saved?`<div class="panel"><h2>Presupuesto frente a gasto real</h2><div class="table-wrap"><table><thead><tr><th>CATEGORÍA</th><th>PRESUPUESTO</th><th>GASTO REAL</th><th>DISPONIBLE / EXCESO</th></tr></thead><tbody>${b.saved.allocations.map((r,i)=>{const planned=allocated(amount,b.saved.allocations)[i],spent=actual(r.category_id);return `<tr><td>${esc(categories().find(c=>c.id===r.category_id)?.name||'Categoría')}</td><td>${euro(planned)}</td><td>${euro(spent)}</td><td>${planned-spent<0?'Exceso: ':''}${euro(Math.abs(planned-spent))}</td></tr>`;}).join('')}</tbody></table></div><p>Gastos personales del mes de actividad seleccionado, incluidas devoluciones. Los gastos de categorías sin presupuesto suman ${euro(U.data.finance.entries.filter(e=>e.area==='personal'&&e.period===U.month&&e.kind==='expense'&&!e.review&&!b.saved.allocations.some(r=>r.category_id===e.category_id)).reduce((s,e)=>s+e.my_expense,0))}.</p></div>`:'');
 }
 function draw(){
  $('#budget-rows').innerHTML=draft.map((r,i)=>`<div class="form-grid" data-budget-row="${i}"><label>Categoría<select data-budget-category="${i}" required><option value="">Elige categoría</option>${categories().map(c=>`<option value="${esc(c.id)}" ${c.id===r.category_id?'selected':''}>${esc(c.name)}</option>`).join('')}</select></label><label>Porcentaje<input type="number" min="0" max="100" step="0.01" value="${esc(r.percent)}" data-budget-percent="${i}" required></label><div><span data-budget-amount="${i}"></span> ${button('Quitar','budget-remove','quiet',`data-index="${i}"`)}</div></div>`).join('');
  totals();
 }
 function totals(){
  const amount=U.data.budget.saved?.amount??U.data.budget.available;
  const bps=draft.reduce((s,r)=>s+Math.round(Number(r.percent||0)*100),0);
  const amounts=allocated(amount,draft.map(r=>({bps:Math.round(Number(r.percent||0)*100)})));
  draft.forEach((r,i)=>{$(`[data-budget-amount="${i}"]`).textContent=euro(amounts[i]);});
  $('#budget-total').textContent=`Asignado: ${(bps/100).toLocaleString('es-ES')} %. ${bps>10000?'Supera el 100 %.':'Sin asignar: '+euro(amount-amounts.reduce((s,v)=>s+v,0))}`;
 }
 function bind(){
  if(U.page!=='budget')return;
  draw();
  $('#budget-form').addEventListener('input',e=>{
   if(e.target.dataset.budgetPercent!==undefined)draft[Number(e.target.dataset.budgetPercent)].percent=e.target.value;
   if(e.target.dataset.budgetCategory!==undefined)draft[Number(e.target.dataset.budgetCategory)].category_id=e.target.value;
   totals();
  });
  $('#budget-form').addEventListener('click',async e=>{
   const b=e.target.closest('[data-action]');if(!b)return;
   if(b.dataset.action==='budget-add'){draft.push({category_id:'',percent:0});draw();}
   if(b.dataset.action==='budget-remove'){draft.splice(Number(b.dataset.index),1);draw();}
   if(b.dataset.action==='budget-category'){
    const name=prompt('Nombre de la categoría de gasto Personal:');if(!name?.trim())return;
    try{await api('/api/category',{name,area:'personal',kind:'expense'});await load();}catch(err){toast(err.message);}
   }
  });
  $('#budget-form').addEventListener('submit',async e=>{
   e.preventDefault();const b=$('button[type=submit]',e.target);b.disabled=true;
   try{await api('/api/budget',{month:U.month,allocations:draft});draft=null;await load();toast('Presupuesto guardado');}catch(err){$('.error',e.target).textContent=err.message;}finally{b.disabled=false;}
  });
 }
 return {render,bind};
}
