import { z } from 'zod';



const PHONE_PATTERN = /^0(3|5|7|8|9)\d{8}$/;


export function normalizePhone(raw) {
  let phone = raw.replace(/[\s.\-()]/g, '');
  if (phone.startsWith('+84')) phone = `0${phone.slice(3)}`;
  else if (phone.startsWith('84') && phone.length === 11) phone = `0${phone.slice(2)}`;
  return phone;
}

export const emailField = z
  .string()
  .trim()
  .min(1, 'Enter your email address')
  .max(100, 'Email must be 100 characters or fewer')
  .pipe(z.email('Enter a valid email address'))
  .transform((value) => value.toLowerCase());

export const phoneField = z
  .string()
  .trim()
  .min(1, 'Enter your phone number')
  .transform(normalizePhone)
  .pipe(z.string().regex(PHONE_PATTERN, 'Enter a valid Vietnamese mobile number, e.g. 0912 345 678'));



export const newPasswordField = z
  .string()
  .min(8, 'Password must be at least 8 characters')
  .max(128, 'Password must be 128 characters or fewer')
  .regex(/[A-Za-z]/, 'Password must include at least one letter')
  .regex(/\d/, 'Password must include at least one number');

export const operatingDaysField = z
  .array(z.number().int().min(1).max(7))
  .min(1, 'Select at least one operating day')
  .refine((days) => new Set(days).size === days.length, 'Each day can be selected once');


export const textField = (name, prompt, min, max) =>
  z
    .string()
    .trim()
    .min(1, `Enter ${prompt}`)
    .min(min, `${name} must be at least ${min} characters`)
    .max(max, `${name} must be ${max} characters or fewer`);



const passwordsMatch = (newKey) => (values) => values[newKey] === values.confirm_password;
const MISMATCH = { message: 'Passwords do not match', path: ['confirm_password'] };

export const loginSchema = z.object({
  email: emailField,
  password: z.string().min(1, 'Enter your password'),
});

export const registerFarmerSchema = z
  .object({
    email: emailField,
    phone: phoneField,
    password: newPasswordField,
    confirm_password: z.string().min(1, 'Confirm your password'),
    stall_name: textField('Stall name', 'a stall name', 2, 100),
    contact_person: textField('Contact person', 'a contact person', 2, 100),
    address: textField('Address', 'an address', 5, 255),
    operating_days: operatingDaysField,
  })
  .refine(passwordsMatch('password'), MISMATCH);


export const REGISTER_FARMER_STEP_1 = ['email', 'phone', 'password', 'confirm_password'];

export const registerCustomerSchema = z
  .object({
    email: emailField,
    full_name: textField('Full name', 'your full name', 2, 100),
    phone: phoneField,
    address: textField('Address', 'an address', 5, 255),
    password: newPasswordField,
    confirm_password: z.string().min(1, 'Confirm your password'),
  })
  .refine(passwordsMatch('password'), MISMATCH);

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: newPasswordField,
    confirm_password: z.string().min(1, 'Confirm your new password'),
  })
  .refine(passwordsMatch('new_password'), MISMATCH);
