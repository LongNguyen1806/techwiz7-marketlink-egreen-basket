import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { toggleOrdering } from '../../utils/ordering';
import '../../styles/common/SortableTh.css';

export function SortableTh({ column, current, onSort, children }) {
  const active = current === column || current === `-${column}`;
  const descending = current === `-${column}`;
  const Icon = !active ? ChevronsUpDown : descending ? ArrowDown : ArrowUp;

  return (
    <th
      className="page-primitive__table-th"
      aria-sort={!active ? 'none' : descending ? 'descending' : 'ascending'}
    >
      <button
        type="button"
        className={`sortable-th${active ? ' sortable-th--active' : ''}`}
        onClick={() => onSort(toggleOrdering(current, column))}
      >
        {children}
        <Icon className="sortable-th__icon" aria-hidden />
      </button>
    </th>
  );
}
