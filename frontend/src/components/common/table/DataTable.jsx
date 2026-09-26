import PropTypes from 'prop-types';
import { cn } from '../../../lib/cn';
import './DataTable.css';

/**
 * The shared table behind every list screen (C-04, F-02, A-02 → A-11). It renders records only;
 * paging, sorting and filtering stay with the screen, which owns the query.
 *
 * A row is only focusable when `onRowClick` is given, so a read-only table keeps a clean tab order.
 */
export function DataTable({
  columns,
  rows,
  rowKey,
  caption,
  emptyMessage = 'Nothing to show yet.',
  isLoading = false,
  onRowClick,
  className,
}) {
  if (isLoading) {
    return (
      <p className="data-table__loading" role="status">
        Loading…
      </p>
    );
  }

  if (rows.length === 0) {
    return <p className="data-table__empty">{emptyMessage}</p>;
  }

  const activate = (row) => () => onRowClick?.(row);
  const onKeyDown = (row) => (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onRowClick?.(row);
    }
  };

  return (
    <div className={cn('data-table', className)}>
      <table className="data-table__table">
        {caption ? <caption className="data-table__caption">{caption}</caption> : null}
        <thead className="data-table__head">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cn('data-table__th', column.align === 'end' && 'data-table__th--end')}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={cn('data-table__row', onRowClick && 'data-table__row--clickable')}
              onClick={onRowClick ? activate(row) : undefined}
              onKeyDown={onRowClick ? onKeyDown(row) : undefined}
              tabIndex={onRowClick ? 0 : undefined}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={cn('data-table__td', column.align === 'end' && 'data-table__td--end')}
                >
                  {column.render ? column.render(row) : row[column.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

DataTable.propTypes = {
  columns: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      header: PropTypes.node.isRequired,
      render: PropTypes.func,
      align: PropTypes.oneOf(['start', 'end']),
    }),
  ).isRequired,
  rows: PropTypes.array.isRequired,
  rowKey: PropTypes.func.isRequired,
  caption: PropTypes.string,
  emptyMessage: PropTypes.node,
  isLoading: PropTypes.bool,
  onRowClick: PropTypes.func,
  className: PropTypes.string,
};
