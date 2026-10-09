import test from 'node:test';
import assert from 'node:assert/strict';
import {assignImportArea,assignImportCategory} from '../static/import-utils.mjs';

const categories=[
 {id:'food',area:'personal',kind:'expense'},
 {id:'platform',area:'academia',kind:'expense'},
 {id:'specific',area:'academia',kind:'expense'},
 {id:'classes',area:'baile',kind:'income'},
];
const rules=[{area:'academia',term:'PLATAFORMA',category_id:'platform'},
 {area:'academia',term:'PLATAFORMA CLASES',category_id:'specific'}];
const row={area:'personal',kind:'expense',amount:-10000,account_id:'personal',date:'2026-09-23',
 description:'Plataforma clases online',category_id:'food',source_key:'bank-123',selected:false,duplicate:true};

test('Cambiar área conserva el banco y aplica la regla más específica del área nueva',()=>{
 const result=assignImportArea(row,'academia',categories,rules);
 assert.deepEqual(result,{...row,area:'academia',category_id:'specific'});
 assert.equal(row.area,'personal');
});
test('Cambiar a un área sin regla elimina la categoría incompatible',()=>{
 assert.equal(assignImportArea(row,'baile',categories,rules).category_id,null);
});
test('Una categoría manual debe coincidir con área y sentido',()=>{
 assert.throws(()=>assignImportCategory(row,'classes',categories));
 assert.throws(()=>assignImportCategory(row,'platform',categories));
 assert.equal(assignImportCategory(row,'',categories).category_id,null);
 assert.equal(assignImportCategory(row,'food',categories).category_id,'food');
});
