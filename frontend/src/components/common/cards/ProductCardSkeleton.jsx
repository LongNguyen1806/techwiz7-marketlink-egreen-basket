import PropTypes from 'prop-types';
import { Skeleton } from '../../ui/Skeleton';
import { cn } from '../../../lib/cn';
import './ProductCard.css';

/**
 * A product card while its data loads, with the same frame, spacing and rows as the real
 * one, so the grid does not jump when the products arrive.
 */
export function ProductCardSkeleton({ className }) {
  return (
    <div className={cn('product-card', 'product-card--skeleton', className)} aria-hidden>
      <Skeleton className="product-card__media product-card__skeleton-media" />
      <div className="product-card__body">
        <Skeleton className="product-card__skeleton-line product-card__skeleton-line--xs" />
        <Skeleton className="product-card__skeleton-line product-card__skeleton-line--title" />
        <Skeleton className="product-card__skeleton-line product-card__skeleton-line--sm" />
        <div className="product-card__meta-row">
          <Skeleton className="product-card__skeleton-line product-card__skeleton-line--price" />
          <Skeleton className="product-card__skeleton-line product-card__skeleton-line--rating" />
        </div>
      </div>
      <div className="product-card__footer">
        <Skeleton className="product-card__skeleton-button" />
      </div>
    </div>
  );
}

ProductCardSkeleton.propTypes = { className: PropTypes.string };

/** A grid's worth of skeleton cards, announced once to screen readers. */
export function ProductCardSkeletonGrid({ count, className }) {
  return (
    <div className={className} aria-busy role="status" aria-label="Loading produce">
      {Array.from({ length: count }).map((_, index) => (
        <ProductCardSkeleton key={index} />
      ))}
    </div>
  );
}

ProductCardSkeletonGrid.propTypes = {
  count: PropTypes.number.isRequired,
  className: PropTypes.string,
};
