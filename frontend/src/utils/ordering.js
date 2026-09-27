export function toggleOrdering(current, column) {
  return current === column ? `-${column}` : column;
}
