import { toast } from 'sonner';
import { useGeoStore } from '../stores/geo.store';
export function useGeolocation() {
    const setCoords = useGeoStore((s) => s.setCoords);
    const lat = useGeoStore((s) => s.latitude);
    const lng = useGeoStore((s) => s.longitude);
    const requestLocation = () => {
        if (!navigator.geolocation) {
            toast.error('Geolocation is not supported by this browser');
            return;
        }
        navigator.geolocation.getCurrentPosition((pos) => {
            setCoords(pos.coords.latitude, pos.coords.longitude);
            toast.success('Location updated');
        }, () => {
            toast.error('Location unavailable — allow access in your browser settings.');
        }, { enableHighAccuracy: true, timeout: 10000 });
    };
    return { lat, lng, requestLocation };
}
