import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import { OSM_ATTRIBUTION, OSM_TILE_URL } from '../../../lib/map';

import './MarketsMap.css';

export function MiniMap({ latitude, longitude, label, className }) {
  return (
    <div className={className}>
      <MapContainer
        center={[latitude, longitude]}
        zoom={15}
        className="mini-map__leaflet"
        scrollWheelZoom={false}
      >
        <TileLayer url={OSM_TILE_URL} attribution={OSM_ATTRIBUTION} />
        <Marker position={[latitude, longitude]}>
          {label ? <Popup>{label}</Popup> : null}
        </Marker>
      </MapContainer>
    </div>
  );
}
