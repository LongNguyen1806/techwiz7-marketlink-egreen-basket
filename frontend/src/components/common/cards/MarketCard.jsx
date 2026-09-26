import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { FavoriteButton } from '../favorites/FavoriteButton';
import { DirectionsButton } from '../maps/DirectionsButton';
import { LazyImage } from '../LazyImage';
import { Badge } from '../../ui/Badge';
import { DAY_OF_WEEK_LABELS } from '../../../utils/helpers/geo';
import { cn } from '../../../lib/cn';
import './MarketCard.css';


export function MarketCard({ market, highlighted = false, onHover, onRequireSignIn, className }) {
  return (
    <article
      className={cn('market-card', highlighted && 'is-highlighted', className)}
      onMouseEnter={() => onHover?.(market.id)}
      onMouseLeave={() => onHover?.(null)}
    >
      <Link to={`/markets/${market.id}`} className="market-card__media-link" aria-hidden tabIndex={-1}>
        <div className="market-card__media">
          <LazyImage src={market.image ?? ''} alt="" className="market-card__image" />
          {market.distance_km !== null && market.distance_km !== undefined ? (
            <Badge className="market-card__distance" variant="secondary">
              {market.distance_km.toFixed(1)} km
            </Badge>
          ) : null}
        </div>
      </Link>

      <div className="market-card__body">
        <div className="market-card__head">
          <Link to={`/markets/${market.id}`} className="market-card__title-link">
            <h3 className="market-card__title">{market.name}</h3>
            <p className="market-card__address">
              <MapPin className="market-card__pin" aria-hidden />
              <span className="market-card__address-text">{market.address}</span>
            </p>
          </Link>
          <FavoriteButton
            kind="markets"
            id={market.id}
            isFavorite={market.is_favorite ?? false}
            onRequireSignIn={onRequireSignIn}
          />
        </div>

        <div className="market-card__days">
          {(market.operating_days ?? []).map((day) => (
            <Badge key={day} variant="outline">{DAY_OF_WEEK_LABELS[day]}</Badge>
          ))}
        </div>

        <div className="market-card__actions">
          <p className="market-card__meta">
            {market.open_time}–{market.close_time} · {market.farmer_count} stalls
          </p>
          <DirectionsButton latitude={market.latitude} longitude={market.longitude} />
        </div>
      </div>
    </article>
  );
}

MarketCard.propTypes = {
  market: PropTypes.object.isRequired,
  highlighted: PropTypes.bool,
  onHover: PropTypes.func,
  onRequireSignIn: PropTypes.func,
  className: PropTypes.string,
};
