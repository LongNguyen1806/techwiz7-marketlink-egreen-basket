import { z } from 'zod';
import { operatingDaysField, phoneField, textField } from '../common/auth.schema';
import { DEFAULT_MAX_UPLOAD_MB, imageFileError } from './product.schema';

// accounts/farmer/serializers_farmer.py FarmerProfileUpdateSerializer.
export function makeFarmerProfileSchema({ maxUploadMb = DEFAULT_MAX_UPLOAD_MB } = {}) {
  return z.object({
    stall_name: textField('Stall name', 'a stall name', 2, 100),
    contact_person: textField('Contact person', 'a contact person', 2, 100),
    phone: phoneField,
    address: textField('Address', 'an address', 5, 255),
    description: z.string().trim().max(1000, 'About must be 1000 characters or fewer'),
    operating_days: operatingDaysField,
    order_cutoff_hours: z
      .number({ error: 'Enter a number of hours' })
      .int('Use whole hours')
      .min(1, 'Cut-off must be at least 1 hour')
      .max(72, 'Cut-off can be at most 72 hours'),
    // A newly picked stall photo; null keeps the current one.
    image: z
      .instanceof(File)
      .nullable()
      .refine((file) => !file || !imageFileError(file, maxUploadMb), {
        error: (issue) => imageFileError(issue.input, maxUploadMb) ?? 'Choose a valid image',
      }),
  });
}

export const PROFILE_FIELDS = [
  'stall_name',
  'contact_person',
  'phone',
  'address',
  'description',
  'operating_days',
  'order_cutoff_hours',
  'image',
];

export function profileToFormValues(profile) {
  return {
    stall_name: profile.stall_name ?? '',
    contact_person: profile.contact_person ?? '',
    phone: profile.phone ?? '',
    address: profile.address ?? '',
    description: profile.description ?? '',
    operating_days: profile.operating_days ?? [],
    // 12 is the FarmerProfile.order_cutoff_hours model default.
    order_cutoff_hours: profile.order_cutoff_hours ?? 12,
    image: null,
  };
}
