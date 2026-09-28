import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ordersApi } from '../../../services/customer/ordersApi';
import { ApiError } from '../../../lib/ApiError';
import { useCartStore } from '../../../stores/cart.store';
import { toCartLine } from '../../common/useAddToCart';


export function useReorder() {
  const navigate = useNavigate();
  const addItem = useCartStore((state) => state.addItem);

  return useMutation({
    mutationFn: ordersApi.reorderPreview,
    onSuccess: ({ items, skipped }) => {
      items.forEach(({ product, quantity }) => addItem(toCartLine(product), quantity));

      if (skipped.length > 0) {
        const names = skipped.map((row) => row.product_name).join(', ');
        toast.message(`Not added, no longer available: ${names}`);
      }
      if (items.length > 0) {
        toast.success(`${items.length} item(s) added to your cart at today's prices`);
        navigate('/customer/cart');
      }
    },
    onError: (error) => {
      toast.error(ApiError.fromUnknown(error).friendlyMessage);
    },
  });
}
