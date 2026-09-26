import { z } from 'zod';
import { textField } from '../common/auth.schema';




export const PRODUCT_UNITS = ['KG', 'BUNCH', 'PIECE', 'PACK'];
export const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
export const DEFAULT_MAX_UPLOAD_MB = 2;

const PRICE_PATTERN = /^\d{1,8}(\.\d{1,2})?$/;


export function imageFileError(file, maxUploadMb = DEFAULT_MAX_UPLOAD_MB) {
  if (!IMAGE_TYPES.includes(file.type)) return 'Choose a JPG, PNG or WEBP image';
  if (file.size > maxUploadMb * 1024 * 1024) return `The image must be ${maxUploadMb} MB or smaller`;
  return null;
}

export function makeProductSchema({ maxUploadMb = DEFAULT_MAX_UPLOAD_MB } = {}) {
  return z.object({
    name: textField('Product name', 'a product name', 2, 100),
    category_id: z.number({ error: 'Select a category' }).int().positive('Select a category'),
    unit: z.enum(PRODUCT_UNITS, { error: 'Select a unit' }),
    price: z
      .string()
      .trim()
      .min(1, 'Enter a price')
      .regex(PRICE_PATTERN, 'Use a price such as 12.50')
      .refine((value) => Number(value) >= 0.01 && Number(value) <= 10000, 'Price must be between $0.01 and $10,000'),
    stock_quantity: z
      .number({ error: 'Enter the stock' })
      .int('Stock must be a whole number')
      .min(0, 'Stock cannot be negative'),
    
    weekly_default_quantity: z
      .number({ error: 'Enter a whole number or leave it blank' })
      .int('Weekly default must be a whole number')
      .min(0, 'Weekly default cannot be negative')
      .nullable(),
    description: z.string().trim().max(1000, 'Description must be 1000 characters or fewer'),
    is_available: z.boolean(),
    
    image: z
      .instanceof(File)
      .nullable()
      .refine((file) => !file || !imageFileError(file, maxUploadMb), {
        error: (issue) => imageFileError(issue.input, maxUploadMb) ?? 'Choose a valid image',
      }),
  });
}

export const PRODUCT_DEFAULTS = {
  name: '',
  category_id: 0,
  unit: 'KG',
  price: '',
  stock_quantity: 0,
  weekly_default_quantity: null,
  description: '',
  is_available: true,
  image: null,
};

export function productToFormValues(product) {
  return {
    name: product.name,
    category_id: product.category?.id ?? 0,
    unit: product.unit,
    price: String(product.price),
    stock_quantity: product.stock_quantity,
    weekly_default_quantity: product.weekly_default_quantity ?? null,
    description: product.description ?? '',
    is_available: product.is_available,
    image: null,
  };
}
