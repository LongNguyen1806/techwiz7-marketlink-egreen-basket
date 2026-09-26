import PropTypes from 'prop-types';
import { Star } from 'lucide-react';
import { cn } from '../../lib/cn';
import '../../styles/common/RatingStars.css';

export function RatingStars({ value, count, size = 'sm', className }) {
  const display = value === null || value === undefined ? '—' : Number(value).toFixed(1);
  return (
    <div className={cn('rating-stars', className)}>
      <Star className={cn('rating-stars__icon', size === 'md' && 'rating-stars__icon--md')} aria-hidden />
      <span className="rating-stars__value">{display}</span>
      {count !== undefined ? <span className="rating-stars__count">({count})</span> : null}
    </div>
  );
}

RatingStars.propTypes = {
  // The API sends averages as numbers or decimal strings ("4.50"), or null when unrated.
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  count: PropTypes.number,
  size: PropTypes.oneOf(['sm', 'md']),
  className: PropTypes.string,
};
