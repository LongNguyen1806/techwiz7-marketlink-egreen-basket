import { useState } from 'react';
import { toast } from 'sonner';

import { adminApi } from '@/api/admin/adminApi';
import { ApiError } from '@/lib/ApiError';

export function useCsvDownload(kind) {
  const [pending, setPending] = useState(false);

  const download = async (params = {}) => {
    setPending(true);
    try {
      const blob = await adminApi.exportCsv(kind, params);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${kind}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) {
      toast.error(ApiError.fromUnknown(error).friendlyMessage);
    } finally {
      setPending(false);
    }
  };

  return { download, pending };
}
