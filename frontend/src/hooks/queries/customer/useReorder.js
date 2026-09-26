import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { ordersApi } from '../../../services/customer/ordersApi';
import { ApiError } from '../../../lib/ApiError';
import { useCartStore } from '../../../stores/cart.store';

/**
 * CU-09 (C-04, C-05). The preview writes nothing: it returns what can be bought again at today's
 * prices, plus what it had to leave out. Those leftovers are named out loud — a silent reorder that
 * quietly drops half the lines is worse than no reorder.
 */
export function useReorder() {
  const navigate = useNavigate();
  const addItem = useCartStore((state) => state.addItem);

  return useMutation({
    mutationFn: ordersApi.reorderPreview,
    onSuccess: ({ items, skipped }) => {
      items.forEach(({ product, quantity }) => {
        addItem({
          product_id: product.id,
          farmer_id: product.farmer.id,
          farmer_stall_name: product.farmer.stall_name,
          name: product.name,
          unit: product.unit,
          price: product.price,
          image: product.image,
        }, quantity);
      });

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
