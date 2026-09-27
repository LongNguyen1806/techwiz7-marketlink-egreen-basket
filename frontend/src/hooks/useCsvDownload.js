import { useState } from 'react';
import { toast } from 'sonner';

import { adminApi } from '@/api/admin/adminApi';
import { ApiError } from '@/lib/ApiError';

/**
 * Downloads an admin list as CSV using the filters currently on screen.
 *
 * The file arrives as a blob rather than a URL the browser can follow, because the endpoint
 * needs the Authorization header that a plain link would not send.
 */
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
      // Released on the next tick so the click has taken the data first.
      setTimeout(() => URL.revokeObjectURL(url), 0);
    } catch (error) {
      toast.error(ApiError.fromUnknown(error).friendlyMessage);
    } finally {
      setPending(false);
    }
  };

  return { download, pending };
}
