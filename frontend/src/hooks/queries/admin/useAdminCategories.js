import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '../../../lib/ApiError';
import { adminApi } from '../../../api/admin/adminApi';

export function useAdminCategories() {
  return useQuery({
    queryKey: ['admin', 'categories'],
    queryFn: adminApi.getCategories,
  });
}

export function useReorderCategories() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids) => adminApi.reorderCategories(ids),
    // Returned, not fired and forgotten: the drag stays pending until the refreshed list is
    // in the cache, so the page never shows the optimistic order next to stale counts.
    onSuccess: () => {
      toast.success('Category order saved');
      return queryClient.invalidateQueries({
        queryKey: ['admin', 'categories'],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => adminApi.createCategory(payload),
    onSuccess: () => {
      toast.success('Category added');
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'categories'],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useDeleteCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.deleteCategory,
    onSuccess: () => {
      toast.success('Category removed');
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'categories'],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
