import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { adminApi } from '@/api/admin/adminApi';

export function useAdminAnnouncements() {
  return useQuery({
    queryKey: ['admin', 'announcements'],
    queryFn: adminApi.getAnnouncements,
  });
}

export function useCreateAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload) => adminApi.createAnnouncement(payload),
    onSuccess: () => {
      toast.success('Announcement created');
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'announcements'],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useDeleteAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adminApi.deleteAnnouncement,
    onSuccess: () => {
      toast.success('Announcement removed');
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'announcements'],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}

export function useToggleAnnouncement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_active }) =>
      adminApi.updateAnnouncement(id, { is_active }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['admin', 'announcements'],
      });
    },
    onError: (e) => toast.error(ApiError.fromUnknown(e).friendlyMessage),
  });
}
