import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { favoritesApi, IDS_FIELD } from '../../../services/customer/favoritesApi';
import { ApiError } from '../../../lib/ApiError';
import { QUERY_KEYS, ROLES } from '../../../constants';
import { useAuth } from '../../authentication/useAuth';

const EMPTY_IDS = { farmer_ids: [], product_ids: [], market_ids: [] };

function withToggled(ids, kind, id, next) {
  const field = IDS_FIELD[kind];
  const current = ids?.[field] ?? [];
  return {
    ...(ids ?? EMPTY_IDS),
    [field]: next ? [...current, id] : current.filter((value) => value !== id),
  };
}


export function useFavorites() {
  const queryClient = useQueryClient();
  const { role } = useAuth();
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


export function useFavoriteList(kind, page = 1) {
  return useQuery({
    queryKey: QUERY_KEYS.CUSTOMER_FAVORITES(kind, page),
    queryFn: () => favoritesApi.list({ kind, page }),
  });
}
