import PropTypes from 'prop-types';
import { Navigation } from 'lucide-react';
import { Button } from '../../ui/Button';
import { googleMapsDirectionsUrl } from '../../../utils/helpers/geo';
import './DirectionsButton.css';

/**
 * Hand the pickup point over to the phone's map app. D-012 keeps Leaflet for everything drawn
 * in-app and uses Google Maps only for this outward link.
 */
export function DirectionsButton({ latitude, longitude, size = 'sm', className }) {
  if (latitude === null || latitude === undefined || longitude === null || longitude === undefined) {
    return null;
  }

  return (
    <Button asChild variant="outline" size={size} className={className}>
      <a
        className="directions-button"
        href={googleMapsDirectionsUrl(latitude, longitude)}
        target="_blank"
        rel="noreferrer"
      >
        <Navigation className="directions-button__icon" aria-hidden />
        Directions
      </a>
    </Button>
  );
}

DirectionsButton.propTypes = {
  latitude: PropTypes.number,
  longitude: PropTypes.number,
  size: PropTypes.oneOf(['default', 'sm', 'lg']),
  className: PropTypes.string,
};
