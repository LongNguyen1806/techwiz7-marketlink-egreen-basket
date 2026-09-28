import { z } from 'zod';

const PRICE_PATTERN = /^\d{1,5}(\.\d{1,2})?$/;

const price = (label) =>
  z
    .string()
    .trim()
    .min(1, `Enter the ${label}`)
    .regex(PRICE_PATTERN, 'Use a price such as 12.50')
    .refine((value) => Number(value) >= 0.01 && Number(value) <= 10000, 'Between $0.01 and $10,000');

export const priceGuidelineSchema = z
  .object({
    category: z.number({ error: 'Select a category' }).int().positive('Select a category'),
    unit: z.enum(['KG', 'BUNCH', 'EACH', 'BAG', 'BOX', 'PACK'], { error: 'Select a unit' }),
    min_price: price('lowest usual price'),
    max_price: price('highest usual price'),
    max_stock: z
      .number({ error: 'Enter a whole number or leave it blank' })
      .int('Use a whole number')
      .min(1, 'At least 1')
      .nullable(),
  })
  .superRefine(({ min_price: low, max_price: high }, ctx) => {
    if (low && high && Number(low) > Number(high)) {
      ctx.addIssue({ code: 'custom', path: ['min_price'], message: 'The lowest price cannot be above the highest' });
    }
  });

export const PRICE_GUIDELINE_DEFAULTS = { category: 0, unit: 'KG', min_price: '', max_price: '', max_stock: null };

export function guidelineToFormValues(guideline) {
  return {
    category: guideline.category,
    unit: guideline.unit,
    min_price: String(guideline.min_price),
    max_price: String(guideline.max_price),
    max_stock: guideline.max_stock ?? null,
  };
}
