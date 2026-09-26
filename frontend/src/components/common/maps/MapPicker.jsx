import PropTypes from 'prop-types';
import { MapContainer, Marker, TileLayer, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import { Button } from '../../ui/Button';
import { cn } from '../../../lib/cn';
import './MapPicker.css';

// Vite hashes the bundled images, so Leaflet's own relative icon paths would 404 without this.
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

/** Coordinates are DECIMAL(9,6) / DECIMAL(10,6) in the database, so six places is the full precision. */
const PRECISION = 6;
const DEFAULT_CENTER = [10.762622, 106.660172]; // Ho Chi Minh City, used only before a point exists

function round(value) {
  return Number(value.toFixed(PRECISION));
}

function ClickToPick({ onPick, readOnly }) {
  useMapEvents({
    click: (event) => {
      if (readOnly) return;
      onPick({ latitude: round(event.latlng.lat), longitude: round(event.latlng.lng) });
    },
  });
  return null;
}

ClickToPick.propTypes = {
  onPick: PropTypes.func.isRequired,
  readOnly: PropTypes.bool,
};

/**
 * Pick a point on the map (A-06 for a market, F-08 for a stall). Both coordinates move together:
 * the database requires them to be both set or both NULL, and a farmer with none falls back to the
 * market position (D-032).
 */
export function MapPicker({ latitude, longitude, onChange, readOnly = false, className }) {
  const hasPoint = latitude !== null && latitude !== undefined && longitude !== null && longitude !== undefined;
  const center = hasPoint ? [latitude, longitude] : DEFAULT_CENTER;

  return (
    <div className={cn('map-picker', className)}>
      <MapContainer center={center} zoom={hasPoint ? 15 : 12} className="map-picker__leaflet">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickToPick onPick={onChange} readOnly={readOnly} />
        {hasPoint ? <Marker position={[latitude, longitude]} /> : null}
      </MapContainer>

      <div className="map-picker__bar">
        {hasPoint ? (
          <p className="map-picker__value">
            <span className="map-picker__coord">{latitude.toFixed(PRECISION)}</span>
            {', '}
            <span className="map-picker__coord">{longitude.toFixed(PRECISION)}</span>
          </p>
        ) : (
          <p className="map-picker__value map-picker__value--empty">
            No location chosen{readOnly ? '' : ' — click the map to drop a pin'}
          </p>
        )}

        {!readOnly && hasPoint ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => onChange({ latitude: null, longitude: null })}
          >
            Clear
          </Button>
        ) : null}
      </div>
    </div>
  );
}

MapPicker.propTypes = {
  latitude: PropTypes.number,
  longitude: PropTypes.number,
  onChange: PropTypes.func.isRequired,
  readOnly: PropTypes.bool,
  className: PropTypes.string,
};
