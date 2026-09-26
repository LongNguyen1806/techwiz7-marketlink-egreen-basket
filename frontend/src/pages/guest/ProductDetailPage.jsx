import { useState } from 'react';
import PropTypes from 'prop-types';
import { Link, useParams } from 'react-router-dom';
import { ShoppingCart } from 'lucide-react';
import { LazyImage } from '../../components/common/LazyImage';
import { PriceTag } from '../../components/common/PriceTag';
import { QuantityStepper } from '../../components/common/QuantityStepper';
import { RatingStars } from '../../components/common/RatingStars';
import { ProductCard } from '../../components/common/cards/ProductCard';
import { FavoriteButton } from '../../components/common/favorites/FavoriteButton';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { MAX_QUANTITY } from '../../stores/cart.store';
import { useAddToCart } from '../../hooks/common/useAddToCart';
import {
  usePublicProduct,
  usePublicProductReviews,
  usePublicProducts,
} from '../../hooks/queries/guest/usePublicCatalog';
import { formatDate } from '../../utils/formatters';
import { dayOfWeekLabel, unitLabel } from '../../utils/labels';
import '../../styles/guest/ProductDetailPage.css';

const LOW_STOCK = 10;
const RELATED_SHOWN = 4;
const STARS = ['5', '4', '3', '2', '1'];

function stockBadge(product) {
  if (product.availability === 'UNAVAILABLE') return { label: 'Unavailable', variant: 'danger' };
  if (product.availability === 'OUT_OF_STOCK') return { label: 'Out of stock', variant: 'danger' };
  if (product.stock_quantity <= LOW_STOCK) {
    return { label: `Low stock · ${product.stock_quantity} left`, variant: 'warning' };
  }
  return { label: `${product.stock_quantity} in stock`, variant: 'success' };
}

function ratingFillClass(percent) {
  if (percent === 0) return 'product-detail-page__rating-fill--0';
  return `product-detail-page__rating-fill--${Math.min(5, Math.ceil(percent / 20))}`;
}

function RatingBreakdown({ summary }) {
  if (!summary) return null;
  return STARS.map((star) => {
    const count = summary.distribution?.[star] ?? 0;
    const percent = summary.rating_count === 0 ? 0 : Math.round((count / summary.rating_count) * 100);
    return (
      <div key={star} className="product-detail-page__rating-row">
        <span className="product-detail-page__rating-star-label">{star}★</span>
        <div className="product-detail-page__rating-track" aria-hidden>
          <div className={`product-detail-page__rating-fill ${ratingFillClass(percent)}`} />
        </div>
        <span className="product-detail-page__rating-count">{count}</span>
      </div>
    );
  });
}

RatingBreakdown.propTypes = { summary: PropTypes.object };

function ReviewList({ productId }) {
  const reviewsQuery = usePublicProductReviews(productId);
  const reviews = reviewsQuery.data?.reviews ?? [];

  return (
    <div className="product-detail-page__reviews-layout">
      <Card className="product-detail-page__rating-card">
        <CardHeader>
          <CardTitle>How shoppers rated it</CardTitle>
        </CardHeader>
        <CardContent className="product-detail-page__card-content--stack">
          <RatingBreakdown summary={reviewsQuery.data?.summary} />
        </CardContent>
      </Card>

      <Card className="product-detail-page__comments-card">
        <CardHeader>
          <CardTitle>What shoppers say</CardTitle>
        </CardHeader>
        <CardContent className="product-detail-page__comments-stack">
          {reviewsQuery.isPending ? <p className="product-detail-page__no-comments">Loading reviews…</p> : null}
          {reviewsQuery.isError && !reviewsQuery.data ? (
            <p className="product-detail-page__no-comments">Reviews couldn&apos;t be loaded.</p>
          ) : null}
          {reviewsQuery.data && reviews.length === 0 ? (
            <p className="product-detail-page__no-comments">No reviews yet — be the first to share how it tasted.</p>
          ) : null}
          {reviews.map((review) => (
            <div key={review.id} className="product-detail-page__comment">
              <div className="product-detail-page__comment-head">
                <p className="product-detail-page__comment-author">{review.customer_display_name}</p>
                <RatingStars value={review.rating} />
              </div>
              {review.comment ? <p className="product-detail-page__comment-body">{review.comment}</p> : null}
              <p className="product-detail-page__comment-date">{formatDate(review.created_at)}</p>
              {review.reply ? (
                <div className="product-detail-page__reply">
                  <p className="product-detail-page__reply-title">Reply from the stall</p>
                  <p className="product-detail-page__reply-body">{review.reply}</p>
                </div>
              ) : null}
            </div>
          ))}
          {reviewsQuery.hasNextPage ? (
            <Button
              variant="outline"
              size="sm"
              loading={reviewsQuery.isFetchingNextPage}
              onClick={() => reviewsQuery.fetchNextPage()}
            >
              Show more reviews
            </Button>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

ReviewList.propTypes = { productId: PropTypes.number.isRequired };

function RelatedProducts({ product, onAddToCart, onRequireSignIn }) {
  
  const relatedQuery = usePublicProducts({ category: String(product.category.id), ordering: 'rating', page_size: 5 });
  const related = (relatedQuery.data?.results ?? []).filter((item) => item.id !== product.id).slice(0, RELATED_SHOWN);
  if (related.length === 0) return null;

  return (
    <section className="product-detail-page__related">
      <h2 className="product-detail-page__related-title">You may also like</h2>
      <div className="product-detail-page__related-grid">
        {related.map((item) => (
          <ProductCard key={item.id} product={item} onAddToCart={onAddToCart} onRequireSignIn={onRequireSignIn} />
        ))}
      </div>
    </section>
  );
}

RelatedProducts.propTypes = {
  product: PropTypes.object.isRequired,
  onAddToCart: PropTypes.func.isRequired,
  onRequireSignIn: PropTypes.func.isRequired,
};

function PurchaseBox({ product, onAddToCart }) {
  const [quantity, setQuantity] = useState(1);
  const canAdd = product.availability === 'IN_STOCK' && product.stock_quantity > 0;
  const maxQuantity = Math.max(1, Math.min(product.stock_quantity, MAX_QUANTITY));

  return (
    <div className="product-detail-page__actions">
      <QuantityStepper value={quantity} min={1} max={maxQuantity} onChange={setQuantity} disabled={!canAdd} />
      <Button disabled={!canAdd} onClick={() => onAddToCart(product, quantity)}>
        <ShoppingCart className="product-detail-page__cart-icon" aria-hidden />
        Reserve for pickup
      </Button>
    </div>
  );
}

PurchaseBox.propTypes = {
  product: PropTypes.object.isRequired,
  onAddToCart: PropTypes.func.isRequired,
};

export default function ProductDetailPage() {
  const { id } = useParams();
  const productQuery = usePublicProduct(id);
  const { addToCart, requireSignIn } = useAddToCart();

  if (productQuery.isPending && productQuery.fetchStatus !== 'idle') return <PageSkeleton />;
  if (!productQuery.data) {
    const notFound = !productQuery.isError || productQuery.error?.status === 404;
    return (
      <div className="product-detail-page__empty-wrap">
        {notFound ? (
          <EmptyState
            title="This product is unavailable"
            description="It may have been removed by the stall, or the link is out of date."
          />
        ) : (
          <EmptyState title="This product couldn't be loaded" actionLabel="Try again" onAction={() => productQuery.refetch()} />
        )}
      </div>
    );
  }

  const product = productQuery.data;
  const badge = stockBadge(product);

  return (
    <div className="product-detail-page">
      <div className="product-detail-page__main">
        <div>
          <div className="product-detail-page__media">
            {product.image ? (
              <LazyImage src={product.image} alt={product.name} className="product-detail-page__media-img" />
            ) : (
              <div className="product-detail-page__media-placeholder">Photo coming soon</div>
            )}
          </div>
        </div>

        <div className="product-detail-page__info">
          <div className="product-detail-page__head">
            <div>
              <p className="product-detail-page__category">{product.category.name}</p>
              <h1 className="product-detail-page__title">{product.name}</h1>
              <RatingStars value={product.rating_avg} count={product.rating_count} size="md" />
            </div>
            <FavoriteButton
              kind="products"
              id={product.id}
              isFavorite={Boolean(product.is_favorite)}
              onRequireSignIn={requireSignIn}
            />
          </div>

          <PriceTag amount={product.price} unit={unitLabel(product.unit)} className="product-detail-page__price" />
          <Badge variant={badge.variant}>{badge.label}</Badge>
          {product.description ? <p className="product-detail-page__desc">{product.description}</p> : null}

          <div className="product-detail-page__stall-box">
            <p className="product-detail-page__stall-label">From the stall</p>
            <Link to={`/farmers/${product.farmer.id}`} className="product-detail-page__stall-link">
              {product.farmer.stall_name}
            </Link>
            {product.markets?.map((market) => (
              <p key={market.market_id} className="product-detail-page__market-note">
                At {market.market_name}
                {market.days?.length
                  ? ` · ${[...new Set(market.days)]
                      .sort((a, b) => a - b)
                      .map((day) => dayOfWeekLabel(day, { short: true }))
                      .join(', ')}`
                  : ''}
              </p>
            ))}
          </div>

          
          <PurchaseBox key={product.id} product={product} onAddToCart={addToCart} />
        </div>
      </div>

      <ReviewList productId={product.id} />
      <RelatedProducts product={product} onAddToCart={addToCart} onRequireSignIn={requireSignIn} />
    </div>
  );
}
