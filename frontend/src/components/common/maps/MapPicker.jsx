import PropTypes from 'prop-types';
import { MapContainer, Marker, TileLayer, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Button } from '../../ui/Button';
import { cn } from '../../../lib/cn';
import { MARKER_ICON } from './markerIcon';
import './MapPicker.css';


const PRECISION = 6;
const DEFAULT_CENTER = [10.762622, 106.660172]; 

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
        {hasPoint ? <Marker position={[latitude, longitude]} icon={MARKER_ICON} /> : null}
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
