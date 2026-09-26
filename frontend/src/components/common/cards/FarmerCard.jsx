import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { FavoriteButton } from '../favorites/FavoriteButton';
import { RatingStars } from './RatingStars';
import { Avatar, AvatarFallback, AvatarImage } from '../../ui/Avatar';
import { Badge } from '../../ui/Badge';
import { DAY_OF_WEEK_LABELS } from '../../../utils/helpers/geo';
import { cn } from '../../../lib/cn';
import './FarmerCard.css';


export function FarmerCard({ farmer, onRequireSignIn, className }) {
  return (
    <article className={cn('farmer-card', className)}>
      <div className="farmer-card__row">
        <Link to={`/farmers/${farmer.id}`} aria-hidden tabIndex={-1}>
          <Avatar className="farmer-card__avatar">
            {farmer.image ? <AvatarImage src={farmer.image} alt="" /> : null}
            <AvatarFallback>{farmer.stall_name.slice(0, 2)}</AvatarFallback>
          </Avatar>
        </Link>

        <div className="farmer-card__main">
          <div className="farmer-card__head">
            <Link to={`/farmers/${farmer.id}`} className="farmer-card__title-link">
              <h3 className="farmer-card__title">{farmer.stall_name}</h3>
            </Link>
            <FavoriteButton
              kind="farmers"
              id={farmer.id}
              isFavorite={farmer.is_favorite ?? false}
              onRequireSignIn={onRequireSignIn}
            />
          </div>

          <div className="farmer-card__stats">
            <RatingStars value={farmer.rating_avg} count={farmer.rating_count} />
            <span className="farmer-card__stat">{farmer.in_stock_product_count} products in stock</span>
            {farmer.distance_km !== null && farmer.distance_km !== undefined ? (
              <span className="farmer-card__stat">{farmer.distance_km.toFixed(1)} km</span>
            ) : null}
          </div>

          <div className="farmer-card__days">
            {(farmer.operating_days ?? []).map((day) => (
              <Badge key={day} variant="outline">{DAY_OF_WEEK_LABELS[day]}</Badge>
            ))}
          </div>

          {farmer.markets?.length ? (
            <p className="farmer-card__markets">
              {farmer.markets.map((market) => market.market_name).join(' · ')}
            </p>
          ) : null}
        </div>
      </div>
    </article>
  );
}

FarmerCard.propTypes = {
  farmer: PropTypes.object.isRequired,
  onRequireSignIn: PropTypes.func,
  className: PropTypes.string,
};
