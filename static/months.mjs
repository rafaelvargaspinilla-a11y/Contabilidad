const names=['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
export function monthSelect(current){
 const year=Number(current.slice(0,4)), now=new Date().getFullYear();
 let html='';
 for(let y=Math.min(year,now)-5;y<=Math.max(year,now)+5;y++)for(let m=1;m<=12;m++){
  const value=`${y}-${String(m).padStart(2,'0')}`;
  html+=`<option value="${value}" ${value===current?'selected':''}>${names[m-1]} ${y}</option>`;
 }
 return html;
}
