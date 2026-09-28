import { useEffect } from 'react';
import PropTypes from 'prop-types';
import { CircleMarker, MapContainer, Marker, TileLayer, Tooltip, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import { MARKER_ICON } from '../common/maps/markerIcon';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { distanceKm } from '../../utils/helpers/geo';
import '../../styles/admin/FarmerLocationCard.css';

const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const MARKET_COLOR = '#d97706';

const isPoint = (latitude, longitude) => typeof latitude === 'number' && typeof longitude === 'number';

function FitAll({ points }) {
  const map = useMap();
  const key = JSON.stringify(points);
  useEffect(() => {
    const bounds = JSON.parse(key);
    if (bounds.length === 1) map.setView(bounds[0], 15);
    else if (bounds.length > 1) map.fitBounds(bounds, { padding: [32, 32], maxZoom: 15 });
  }, [key, map]);
  return null;
}

FitAll.propTypes = { points: PropTypes.arrayOf(PropTypes.arrayOf(PropTypes.number)).isRequired };

export function FarmerLocationCard({ address, latitude, longitude, markets = [] }) {
  const hasFarm = isPoint(latitude, longitude);
  const marketPoints = markets.filter((market) => isPoint(market.latitude, market.longitude));
  const points = [
    ...(hasFarm ? [[latitude, longitude]] : []),
    ...marketPoints.map((market) => [market.latitude, market.longitude]),
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Location</CardTitle>
      </CardHeader>
      <CardContent className="farmer-location-card">
        <div>
          <p className="farmer-location-card__label">Farm address</p>
          <p>{address || '—'}</p>
          {hasFarm ? null : (
            <p className="farmer-location-card__warn">
              Location not set: no pin was placed and the address could not be found on the map.
            </p>
          )}
        </div>

        {marketPoints.length && hasFarm ? (
          <ul className="farmer-location-card__distances">
            {marketPoints.map((market) => (
              <li key={market.market_id}>
                {`${market.market_name}: ${distanceKm(latitude, longitude, market.latitude, market.longitude).toFixed(1)} km from the farm`}
              </li>
            ))}
          </ul>
        ) : null}

        {points.length ? (
          <>
            <MapContainer center={points[0]} zoom={13} className="farmer-location-card__map">
              <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILE_URL} />
              <FitAll points={points} />
              {hasFarm ? (
                <Marker position={[latitude, longitude]} icon={MARKER_ICON}>
                  <Tooltip>Farm</Tooltip>
                </Marker>
              ) : null}
              {marketPoints.map((market) => (
                <CircleMarker
                  key={market.market_id}
                  center={[market.latitude, market.longitude]}
                  radius={9}
                  pathOptions={{ color: MARKET_COLOR, fillColor: MARKET_COLOR, fillOpacity: 0.85, weight: 2 }}
                >
                  <Tooltip>{market.market_name}</Tooltip>
                </CircleMarker>
              ))}
            </MapContainer>
            <p className="farmer-location-card__legend">
              <span className="farmer-location-card__legend-farm" aria-hidden /> Farm
              <span className="farmer-location-card__legend-market" aria-hidden /> Market it sells at
            </p>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

FarmerLocationCard.propTypes = {
  address: PropTypes.string,
  latitude: PropTypes.number,
  longitude: PropTypes.number,
  markets: PropTypes.arrayOf(
    PropTypes.shape({
      market_id: PropTypes.number.isRequired,
      market_name: PropTypes.string.isRequired,
      latitude: PropTypes.number,
      longitude: PropTypes.number,
    }),
  ),
};
