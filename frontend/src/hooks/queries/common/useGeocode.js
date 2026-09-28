import { useMutation } from '@tanstack/react-query';
import { geocodeApi } from '../../../api/common/geocodeApi';

export function useGeocode() {
  return useMutation({
    mutationFn: (address) => geocodeApi.lookup(address.trim()),
    meta: { silent: true },
  });
}
