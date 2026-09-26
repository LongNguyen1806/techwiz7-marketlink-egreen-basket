import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ShoppingCart } from 'lucide-react';
import { FavoriteButton } from '../favorites/FavoriteButton';
import { LazyImage } from '../LazyImage';
import { PriceTag } from './PriceTag';
import { RatingStars } from './RatingStars';
import { StockBadge } from '../badges/StockBadge';
import { Button } from '../../ui/Button';
import { cn } from '../../../lib/cn';
import './ProductCard.css';

/**
 * One product, as the catalogue and the favourites page show it (G-04, G-05, C-08).
 *
 * The card never touches the cart itself: `onAddToCart` receives the whole product so the caller
 * decides the quantity and where the line is stored (C-01 keeps it in Zustand). Without a handler
 * the card is a display card, which is what a guest screen needs.
 */
export function ProductCard({ product, onAddToCart, onRequireSignIn, className }) {
  const canAdd = product.availability === 'IN_STOCK' && product.stock_quantity > 0;
  // D-025: only a sell-out can be followed by a restock alert, and the heart is what subscribes.
  const canWatchRestock = product.availability === 'OUT_OF_STOCK';

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('product-card', className)}
    >
      <div className="product-card__media">
        <Link to={`/products/${product.id}`} className="product-card__media-link">
          {product.image ? (
            <LazyImage src={product.image} alt={product.name} className="product-card__image" />
          ) : (
            <div className="product-card__placeholder">No image</div>
          )}
        </Link>
        <div className="product-card__stock-badge">
          <StockBadge availability={product.availability} stockQuantity={product.stock_quantity} />
        </div>
        <div className="product-card__favorite">
          <FavoriteButton
            kind="products"
            id={product.id}
            isFavorite={product.is_favorite ?? false}
            onRequireSignIn={onRequireSignIn}
            className="product-card__favorite-btn"
          />
        </div>
      </div>

      <div className="product-card__body">
        <p className="product-card__category">{product.category.name}</p>
        <Link to={`/products/${product.id}`} className="product-card__title-link">
          <h3 className="product-card__title">{product.name}</h3>
        </Link>
        <Link to={`/farmers/${product.farmer.id}`} className="product-card__stall">
          {product.farmer.stall_name}
        </Link>
        <div className="product-card__meta-row">
          <PriceTag amount={product.price} unit={product.unit} />
          <RatingStars value={product.rating_avg} count={product.rating_count} />
        </div>
      </div>

      <div className="product-card__footer">
        <Button
          className="product-card__add-btn"
          size="sm"
          disabled={!canAdd}
          onClick={() => onAddToCart?.(product)}
        >
          <ShoppingCart className="product-card__cart-icon" aria-hidden />
          Add to cart
        </Button>
        {canWatchRestock ? (
          <p className="product-card__restock">
            Notify when back in stock — save it to your favorites.
          </p>
        ) : null}
      </div>
    </motion.article>
  );
}

ProductCard.propTypes = {
  product: PropTypes.object.isRequired,
  onAddToCart: PropTypes.func,
  onRequireSignIn: PropTypes.func,
  className: PropTypes.string,
};
