import { z } from 'zod';

export const announcementSchema = z.object({
  title: z.string().min(1, 'Enter title'),
  content: z.string().min(1, 'Enter content'),
  audience: z.enum(['ALL', 'CUSTOMER', 'FARMER']),
  starts_at: z.string().min(1, 'Select start time'),
  is_active: z.boolean(),
});
