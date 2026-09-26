import { z } from 'zod';

export const categorySchema = z.object({
  name: z.string().min(1, 'Enter category name'),
  icon: z.string().min(1, 'Enter icon'),
});
