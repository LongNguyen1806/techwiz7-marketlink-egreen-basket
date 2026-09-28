import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import 'leaflet/dist/leaflet.css';

// Every map in the app imports this module, so the setup below runs once.
//
// Leaflet's default marker puts a folder it guesses from leaflet.css in front of the icon URL.
// Vite has already turned that URL into its own asset link (a data: URL for small images), so
// the joined URL pointed nowhere and the pin showed as a broken image. Without _getIconUrl the
// URLs below are used exactly as given.
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

// OSM tile usage policy: "Use exactly: https://tile.openstreetmap.org/{z}/{x}/{y}.png"; other
// hostnames (the old a./b./c. ones included) "may be slower or withdrawn without notice".
// https://operations.osmfoundation.org/policies/tiles/
export const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

// The same policy asks for visible credit to OpenStreetMap on every map.
export const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
