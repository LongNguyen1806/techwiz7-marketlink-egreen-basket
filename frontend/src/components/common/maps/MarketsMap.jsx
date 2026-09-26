import PropTypes from 'prop-types';
import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './MarketsMap.css';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
L.Icon.Default.mergeOptions({
    iconRetinaUrl: markerIcon2x,
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
});
export function MiniMap({ latitude, longitude, label, className, }) {
    return (<div className={className}>
      <MapContainer center={[latitude, longitude]} zoom={15} className="mini-map__leaflet" scrollWheelZoom={false}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
        <Marker position={[latitude, longitude]}>
          {label ? <Popup>{label}</Popup> : null}
        </Marker>
      </MapContainer>
    </div>);
}

MiniMap.propTypes = {
    latitude: PropTypes.number.isRequired,
    longitude: PropTypes.number.isRequired,
    label: PropTypes.string,
    className: PropTypes.string,
};
