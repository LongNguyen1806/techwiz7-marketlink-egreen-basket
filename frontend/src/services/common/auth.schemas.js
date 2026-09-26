import { z } from 'zod';
export const loginSchema = z.object({
    email: z
        .string()
        .min(1, 'Please enter your email')
        .email('Invalid email')
        .transform((v) => v.toLowerCase()),
    password: z.string().min(1, 'Please enter your password'),
});
const phoneSchema = z
    .string()
    .regex(/^(0|\+84)(3|5|7|8|9)\d{8}$/, 'Invalid Vietnamese phone number');
const passwordSchema = z
    .string()
    .min(8, 'Password must be at least 8 characters')
    .regex(/[A-Za-z]/, 'Password must include a letter')
    .regex(/\d/, 'Password must include a number');
// D-031: ISO weekdays, Monday = 1. `normalize_operating_days` sorts them and rejects
// an empty list or a duplicate, so the form has to ask for at least one day.
const operatingDaysSchema = z
    .array(z.number().int().min(1, 'Invalid operating day').max(7, 'Invalid operating day'), {
    error: 'Select at least one operating day',
})
    .min(1, 'Select at least one operating day')
    .refine((days) => new Set(days).size === days.length, 'Operating days must not contain duplicates');
export const registerCustomerSchema = z
    .object({
    email: z
        .string()
        .min(1, 'Please enter your email')
        .email('Invalid email')
        .transform((v) => v.toLowerCase()),
    full_name: z.string().min(2, 'Full name must be at least 2 characters'),
    phone: phoneSchema,
    address: z.string().min(5, 'Please enter your address'),
    password: passwordSchema,
    confirm_password: z.string(),
})
    .refine((data) => data.password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
});
export const registerFarmerSchema = z
    .object({
    email: z
        .string()
        .min(1, 'Please enter your email')
        .email('Invalid email')
        .transform((v) => v.toLowerCase()),
    stall_name: z.string().min(2, 'Stall name must be at least 2 characters'),
    contact_person: z.string().min(2, 'Contact person must be at least 2 characters'),
    phone: phoneSchema,
    address: z.string().min(5, 'Please enter your address'),
    operating_days: operatingDaysSchema,
    password: passwordSchema,
    confirm_password: z.string(),
})
    .refine((data) => data.password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
});
export const changePasswordSchema = z
    .object({
    current_password: z.string().min(1, 'Please enter your current password'),
    new_password: passwordSchema,
    confirm_password: z.string(),
})
    .refine((data) => data.new_password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
});
