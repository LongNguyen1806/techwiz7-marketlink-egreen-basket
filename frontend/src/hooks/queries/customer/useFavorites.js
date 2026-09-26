import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { favoritesApi, IDS_FIELD } from '../../../services/customer/favoritesApi';
import { ApiError } from '../../../lib/ApiError';
import { QUERY_KEYS, ROLES } from '../../../constants';
import { useAuthStore } from '../../../stores/auth.store';

const EMPTY_IDS = { farmer_ids: [], product_ids: [], market_ids: [] };

function withToggled(ids, kind, id, next) {
  const field = IDS_FIELD[kind];
  const current = ids?.[field] ?? [];
  return {
    ...(ids ?? EMPTY_IDS),
    [field]: next ? [...current, id] : current.filter((value) => value !== id),
  };
}

/**
 * The heart, wherever it appears (G-02 → G-06, C-08). CU-12 is read once and shared, so a stall
 * hearted on the catalogue is already hearted on the favourites page.
 *
 * The toggle is optimistic — waiting for a round trip on a heart feels broken (D-019) — and the
 * previous ids are restored if the request fails, so the screen never claims something it lost.
 */
export function useFavorites() {
  const queryClient = useQueryClient();
  const role = useAuthStore((state) => state.role);
  const isCustomer = role === ROLES.CUSTOMER;

  const idsQuery = useQuery({
    queryKey: QUERY_KEYS.FAVORITE_IDS,
    queryFn: favoritesApi.ids,
    enabled: isCustomer,
    staleTime: 60_000,
  });

  const mutation = useMutation({
    mutationFn: ({ kind, id, isFavorite }) =>
      (isFavorite ? favoritesApi.remove({ kind, id }) : favoritesApi.add({ kind, id })),

    onMutate: async ({ kind, id, isFavorite }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.FAVORITE_IDS });
      const previous = queryClient.getQueryData(QUERY_KEYS.FAVORITE_IDS);
      queryClient.setQueryData(QUERY_KEYS.FAVORITE_IDS, (ids) =>
        withToggled(ids, kind, id, !isFavorite));
      return { previous };
    },

    onError: (error, _variables, context) => {
      if (context) queryClient.setQueryData(QUERY_KEYS.FAVORITE_IDS, context.previous);
      toast.error(ApiError.fromUnknown(error).friendlyMessage);
    },

    onSettled: (_data, _error, { kind }) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.FAVORITE_IDS });
      // C-08 lists the hearted rows themselves, so the affected tab has to be refetched too.
      queryClient.invalidateQueries({ queryKey: ['customer-favorites', kind] });
    },
  });

  const ids = idsQuery.data ?? EMPTY_IDS;

  return {
    ids,
    isLoadingIds: idsQuery.isLoading,
    isFavorite: (kind, id) => (ids[IDS_FIELD[kind]] ?? []).includes(id),
    toggle: mutation.mutate,
    isToggling: mutation.isPending,
  };
}

/** One tab of C-08. Paginated, and a row that stops being publicly on sale simply drops out. */
export function useFavoriteList(kind, page = 1) {
  return useQuery({
    queryKey: QUERY_KEYS.CUSTOMER_FAVORITES(kind, page),
    queryFn: () => favoritesApi.list({ kind, page }),
  });
}
