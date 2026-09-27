import { useMutation } from '@tanstack/react-query';
import { geocodeApi } from '../../../api/common/geocodeApi';

/** "Find on map": looks an address up when the person asks, not on every keystroke. */
export function useGeocode() {
  return useMutation({
    mutationFn: (address) => geocodeApi.lookup(address.trim()),
    // The map shows its own message; a toast on top would say the same thing twice.
    meta: { silent: true },
  });
}
