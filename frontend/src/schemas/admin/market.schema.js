import { z } from 'zod';

const dayOfWeekSchema = z.union([
  z.literal(1),
  z.literal(2),
  z.literal(3),
  z.literal(4),
  z.literal(5),
  z.literal(6),
  z.literal(7),
]);

export const marketSchema = z.object({
  name: z.string().min(1, 'Enter market name'),
  address: z.string().min(1, 'Enter address'),
  latitude: z.number(),
  longitude: z.number(),
  image: z.string().optional().nullable(),
  open_time: z.string().min(1, 'Select open time'),
  close_time: z.string().min(1, 'Select close time'),
  operating_days: z.array(dayOfWeekSchema).min(1, 'Select at least one day'),
  description: z.string().optional().nullable(),
});
