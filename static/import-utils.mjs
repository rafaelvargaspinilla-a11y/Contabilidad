// Cambiar la clasificación no cambia el dinero, la cuenta ni la identidad bancaria.
export function assignImportArea(row, area, categories, rules) {
  if (!['academia', 'baile', 'personal'].includes(area)) throw new Error('Área inválida.');
  if (row.error || row.area === area) return row;
  const description = String(row.description || '').toLocaleLowerCase('es');
  const matching = rules.filter(rule => {
    const category = categories.find(c => c.id === rule.category_id);
    return rule.area === area && category?.area === area && category.kind === row.kind
      && description.includes(rule.term.toLocaleLowerCase('es'));
  }).sort((a, b) => b.term.length - a.term.length);
  return {...row, area, category_id: matching[0]?.category_id || null};
}

export function assignImportCategory(row, categoryId, categories) {
  if (row.error) return row;
  if (categoryId && !categories.some(c => c.id === categoryId && c.area === row.area && c.kind === row.kind)) {
    throw new Error('La categoría no corresponde al área y tipo del movimiento.');
  }
  return {...row, category_id: categoryId || null};
}
