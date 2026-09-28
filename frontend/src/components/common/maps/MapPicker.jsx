import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import { LocateFixed } from 'lucide-react';
import 'leaflet/dist/leaflet.css';
import { Button } from '../../ui/Button';
import { useGeocode } from '../../../hooks/queries/common/useGeocode';
import { cn } from '../../../lib/cn';
import { MARKER_ICON } from './markerIcon';
import './MapPicker.css';

const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const PRECISION = 6;
const DEFAULT_CENTER = [10.762622, 106.660172];
const MIN_ADDRESS_LENGTH = 5;

function round(value) {
  return Number(value.toFixed(PRECISION));
}

function ClickToPick({ onPick }) {
  useMapEvents({
    click: (event) => onPick({ latitude: round(event.latlng.lat), longitude: round(event.latlng.lng) }),
  });
  return null;
}

ClickToPick.propTypes = { onPick: PropTypes.func.isRequired };

function FlyToFound({ found }) {
  const map = useMap();
  useEffect(() => {
    if (found) map.setView([found.latitude, found.longitude], Math.max(map.getZoom(), 16));
  }, [found, map]);
  return null;
}

FlyToFound.propTypes = { found: PropTypes.object };

function lookupMessage(geocode) {
  if (geocode.isError) {
    return geocode.error?.status === 429
      ? 'Too many searches in a row. Wait a minute, or place the pin by clicking the map.'
      : "The map search isn't available right now. Place the pin by clicking the map.";
  }
  if (geocode.data && !geocode.data.found) {
    return "We couldn't find that address. Click the map where it is, then drag the pin to adjust.";
  }
  if (geocode.data?.found) return 'Found it. Check the pin and drag it if it is not quite right.';
  return null;
}

export function MapPicker({ latitude = null, longitude = null, onChange, address, readOnly = false, className }) {
  const hasPoint = typeof latitude === 'number' && typeof longitude === 'number';
  const geocode = useGeocode();
  const [searched, setSearched] = useState('');
  const [found, setFound] = useState(null);
  const query = (address ?? '').trim();
  const message = searched && searched === query ? lookupMessage(geocode) : null;

  const find = () => {
    setSearched(query);
    geocode.mutate(query, {
      onSuccess: (result) => {
        if (!result.found) return;
        const point = { latitude: round(result.latitude), longitude: round(result.longitude) };
        onChange(point);
        setFound(point);
      },
    });
  };

  return (
    <div className={cn('map-picker', className)}>
      {address !== undefined && !readOnly ? (
        <div className="map-picker__search">
          <Button
            type="button"
            variant="outline"
            size="sm"
            loading={geocode.isPending}
            disabled={query.length < MIN_ADDRESS_LENGTH}
            onClick={find}
          >
            <LocateFixed className="map-picker__search-icon" aria-hidden />
            Find on map
          </Button>
          {message ? (
            <p
              className={cn('map-picker__message', geocode.data?.found && 'map-picker__message--ok')}
              role="status"
            >
              {message}
            </p>
          ) : null}
        </div>
      ) : null}

      <MapContainer
        center={hasPoint ? [latitude, longitude] : DEFAULT_CENTER}
        zoom={hasPoint ? 16 : 12}
        className="map-picker__leaflet"
      >
        <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILE_URL} />
        <FlyToFound found={found} />
        {readOnly ? null : <ClickToPick onPick={onChange} />}
        {hasPoint ? (
          <Marker
            position={[latitude, longitude]}
            icon={MARKER_ICON}
            draggable={!readOnly}
            eventHandlers={{
              dragend: (event) => {
                const point = event.target.getLatLng();
                onChange({ latitude: round(point.lat), longitude: round(point.lng) });
              },
            }}
          />
        ) : null}
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
          <Button type="button" variant="ghost" size="sm" onClick={() => onChange({ latitude: null, longitude: null })}>
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
  onChange: PropTypes.func,
  address: PropTypes.string,
  readOnly: PropTypes.bool,
  className: PropTypes.string,
};
