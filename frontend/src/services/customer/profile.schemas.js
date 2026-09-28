import { z } from 'zod';
import { imageFileError } from '../../schemas/farmer/product.schema';


export const profileSchema = z.object({
  full_name: z.string().min(2, 'Full name must be at least 2 characters').max(100),
  phone: z.string().regex(/^(0|\+84)(3|5|7|8|9)\d{8}$/, 'Invalid Vietnamese phone number'),
  address: z.string().min(5, 'Please enter your address').max(255),
  image: z
    .instanceof(File)
    .nullable()
    .refine((file) => !file || !imageFileError(file), {
      error: (issue) => imageFileError(issue.input) ?? 'Choose a valid image',
    }),
  remove_image: z.boolean(),
});
