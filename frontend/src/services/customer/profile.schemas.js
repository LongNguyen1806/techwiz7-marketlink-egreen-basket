import { z } from 'zod';

/**
 * C-10, matching CustomerProfileWriteSerializer: the same rules as sign-up, and email is not here
 * at all because CU-03 refuses to change it.
 */
export const profileSchema = z.object({
  full_name: z.string().min(2, 'Full name must be at least 2 characters').max(100),
  phone: z.string().regex(/^(0|\+84)(3|5|7|8|9)\d{8}$/, 'Invalid Vietnamese phone number'),
  address: z.string().min(5, 'Please enter your address').max(255),
});
