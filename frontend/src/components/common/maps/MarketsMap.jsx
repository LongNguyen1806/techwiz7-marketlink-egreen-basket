import { useEffect } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { MARKER_ICON } from './markerIcon';
import './MarketsMap.css';

const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const DEFAULT_CENTER = [10.762622, 106.660172];

const hasPoint = (item) => typeof item.latitude === 'number' && typeof item.longitude === 'number';

export function MiniMap({ latitude, longitude, label, className }) {
  return (
    <div className={className}>
      <MapContainer
        key={`${latitude},${longitude}`}
        center={[latitude, longitude]}
        zoom={15}
        className="mini-map__leaflet"
        scrollWheelZoom={false}
      >
        <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILE_URL} />
        <Marker position={[latitude, longitude]} icon={MARKER_ICON}>
          {label ? <Popup>{label}</Popup> : null}
        </Marker>
      </MapContainer>
    </div>
  );
}

MiniMap.propTypes = {
  latitude: PropTypes.number.isRequired,
  longitude: PropTypes.number.isRequired,
  label: PropTypes.string,
  className: PropTypes.string,
};

function FitToMarkets({ markets }) {
  const map = useMap();
  const boundsKey = markets.map((market) => market.id).join(',');

  useEffect(() => {
    if (markets.length === 0) return;
    if (markets.length === 1) {
      map.setView([markets[0].latitude, markets[0].longitude], 15);
      return;
    }
    map.fitBounds(
      markets.map((market) => [market.latitude, market.longitude]),
      { padding: [32, 32], maxZoom: 15 },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [boundsKey, map]);

  return null;
}

FitToMarkets.propTypes = { markets: PropTypes.arrayOf(PropTypes.object).isRequired };

export function MarketsMap({ markets, highlightedId = null, className }) {
  const points = markets.filter(hasPoint);

  return (
    <div className={className}>
      <MapContainer center={DEFAULT_CENTER} zoom={12} className="mini-map__leaflet">
        <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILE_URL} />
        <FitToMarkets markets={points} />
        {points.map((market) => {
          const faded = highlightedId !== null && highlightedId !== market.id;
          return (
            <Marker
              key={market.id}
              position={[market.latitude, market.longitude]}
              icon={MARKER_ICON}
              opacity={faded ? 0.45 : 1}
              zIndexOffset={highlightedId === market.id ? 1000 : 0}
            >
              <Popup>
                <p className="markets-map__popup-name">{market.name}</p>
                <Link to={`/markets/${market.id}`} className="markets-map__popup-link">
                  View market
                </Link>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}

MarketsMap.propTypes = {
  markets: PropTypes.arrayOf(PropTypes.object).isRequired,
  highlightedId: PropTypes.number,
  className: PropTypes.string,
};
