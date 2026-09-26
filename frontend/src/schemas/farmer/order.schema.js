import { z } from 'zod';

// orders/farmer/serializers_farmer.py DeclineOrderSerializer
export const declineOrderSchema = z.object({
  reason: z
    .string()
    .trim()
    .min(1, 'Tell the shopper why you are declining')
    .min(5, 'Reason must be at least 5 characters')
    .max(500, 'Reason must be 500 characters or fewer'),
  sold_out_product_ids: z.array(z.number().int().positive()),
});

export const DECLINE_DEFAULTS = { reason: '', sold_out_product_ids: [] };
