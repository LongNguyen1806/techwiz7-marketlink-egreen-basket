import PropTypes from 'prop-types';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/cn';
import '../../styles/common/Pagination.css';

export function pageItems(page, totalPages, siblings = 1) {
  const shown = new Set([1, totalPages]);
  for (let number = page - siblings; number <= page + siblings; number += 1) {
    if (number >= 1 && number <= totalPages) shown.add(number);
  }
  const sorted = [...shown].sort((a, b) => a - b);
  const items = [];
  sorted.forEach((number, index) => {
    const previous = sorted[index - 1];
    if (previous !== undefined && number - previous === 2) items.push(previous + 1);
    else if (previous !== undefined && number - previous > 2) items.push(`gap-${number}`);
    items.push(number);
  });
  return items;
}

export function Pagination({ page, totalPages, onChange, disabled = false, className }) {
  if (totalPages <= 1) return null;

  const go = (number) => {
    if (!disabled && number !== page && number >= 1 && number <= totalPages) onChange(number);
  };

  return (
    <nav className={cn('pagination', className)} aria-label="Pagination">
      <button
        type="button"
        className="pagination__step"
        disabled={disabled || page <= 1}
        onClick={() => go(page - 1)}
        aria-label="Previous page"
      >
        <ChevronLeft className="pagination__icon" aria-hidden />
        <span className="pagination__step-label">Prev</span>
      </button>

      <ul className="pagination__list">
        {pageItems(page, totalPages).map((item) =>
          typeof item === 'number' ? (
            <li key={item}>
              <button
                type="button"
                className={cn('pagination__page', item === page && 'pagination__page--current')}
                aria-current={item === page ? 'page' : undefined}
                aria-label={`Page ${item}`}
                disabled={disabled && item !== page}
                onClick={() => go(item)}
              >
                {item}
              </button>
            </li>
          ) : (
            <li key={item} className="pagination__gap" aria-hidden>
              …
            </li>
          ),
        )}
      </ul>

      <button
        type="button"
        className="pagination__step"
        disabled={disabled || page >= totalPages}
        onClick={() => go(page + 1)}
        aria-label="Next page"
      >
        <span className="pagination__step-label">Next</span>
        <ChevronRight className="pagination__icon" aria-hidden />
      </button>
    </nav>
  );
}

Pagination.propTypes = {
  page: PropTypes.number.isRequired,
  totalPages: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  className: PropTypes.string,
};

export function PageStatus({ page, pageSize, total, shown, className }) {
  if (!total || !shown) return null;
  const first = (page - 1) * pageSize + 1;
  return (
    <p className={cn('pagination__status', className)}>{`Showing ${first}–${first + shown - 1} of ${total}`}</p>
  );
}

PageStatus.propTypes = {
  page: PropTypes.number.isRequired,
  pageSize: PropTypes.number.isRequired,
  total: PropTypes.number,
  shown: PropTypes.number,
  className: PropTypes.string,
};
