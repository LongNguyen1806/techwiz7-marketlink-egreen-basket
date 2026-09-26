import { describe, expect, it } from 'vitest';
import {
  changePasswordSchema,
  loginSchema,
  registerCustomerSchema,
  registerFarmerSchema,
} from './auth.schemas';

/** The client rules must not be looser than the serializers, or the form sends a request that 400s. */
const CUSTOMER = {
  email: 'Alice@Example.com',
  full_name: 'Alice Nguyen',
  phone: '0912345678',
  address: '12 Market Street, District 1',
  password: 'Mango2026x',
  confirm_password: 'Mango2026x',
};
const FARMER = {
  email: 'stall@example.com',
  stall_name: 'Green Stall',
  contact_person: 'Bob Tran',
  phone: '0987654321',
  address: '5 Farm Road, Da Lat',
  operating_days: [2, 4, 6],
  password: 'Mango2026x',
  confirm_password: 'Mango2026x',
};

function errorFor(schema, value, field) {
  const result = schema.safeParse(value);
  if (result.success) return null;
  return result.error.issues.find((issue) => issue.path[0] === field) ?? null;
}

describe('loginSchema', () => {
  it('lowercases the email, as the backend does', () => {
    expect(loginSchema.parse({ email: 'Alice@Example.com', password: 'x' }).email)
      .toBe('alice@example.com');
  });

  it('asks for both fields', () => {
    expect(errorFor(loginSchema, { email: '', password: '' }, 'email')).not.toBeNull();
    expect(errorFor(loginSchema, { email: 'a@b.co', password: '' }, 'password')).not.toBeNull();
  });
});

describe('registerCustomerSchema (AU-01)', () => {
  it('accepts a complete form', () => {
    expect(registerCustomerSchema.safeParse(CUSTOMER).success).toBe(true);
  });

  it('wants at least two characters of name, like the serializer', () => {
    expect(errorFor(registerCustomerSchema, { ...CUSTOMER, full_name: 'A' }, 'full_name')).not.toBeNull();
  });

  it('accepts the +84 form of a phone number (D-028)', () => {
    expect(registerCustomerSchema.safeParse({ ...CUSTOMER, phone: '+84912345678' }).success).toBe(true);
  });

  it('rejects a phone number that is not Vietnamese', () => {
    expect(errorFor(registerCustomerSchema, { ...CUSTOMER, phone: '0123456789' }, 'phone')).not.toBeNull();
  });

  it('catches a mistyped confirmation before the request goes out', () => {
    const issue = errorFor(registerCustomerSchema, { ...CUSTOMER, confirm_password: 'Mango2026y' }, 'confirm_password');
    expect(issue?.message).toBe('Passwords do not match');
  });

  it('enforces the password rule of §1.5', () => {
    expect(registerCustomerSchema.safeParse({ ...CUSTOMER, password: 'short1', confirm_password: 'short1' }).success)
      .toBe(false);
    expect(registerCustomerSchema.safeParse({ ...CUSTOMER, password: 'lettersonly', confirm_password: 'lettersonly' }).success)
      .toBe(false);
  });
});

describe('registerFarmerSchema (AU-02)', () => {
  it('accepts a complete form', () => {
    expect(registerFarmerSchema.safeParse(FARMER).success).toBe(true);
  });

  it('requires at least one operating day (D-031)', () => {
    // The serializer rejects an empty list, so the form has to ask for it.
    expect(errorFor(registerFarmerSchema, { ...FARMER, operating_days: [] }, 'operating_days')).not.toBeNull();
    expect(errorFor(registerFarmerSchema, { ...FARMER, operating_days: undefined }, 'operating_days')).not.toBeNull();
  });

  it('takes ISO weekdays only, with no duplicates', () => {
    expect(errorFor(registerFarmerSchema, { ...FARMER, operating_days: [0] }, 'operating_days')).not.toBeNull();
    expect(errorFor(registerFarmerSchema, { ...FARMER, operating_days: [8] }, 'operating_days')).not.toBeNull();
    expect(errorFor(registerFarmerSchema, { ...FARMER, operating_days: [2, 2] }, 'operating_days')).not.toBeNull();
  });

  it('wants at least two characters of contact person, like the serializer', () => {
    expect(errorFor(registerFarmerSchema, { ...FARMER, contact_person: 'B' }, 'contact_person')).not.toBeNull();
  });
});

describe('changePasswordSchema (AU-07)', () => {
  it('keeps confirm_password, which the serializer requires', () => {
    const parsed = changePasswordSchema.parse({
      current_password: 'Mango2026x', new_password: 'Papaya2027z', confirm_password: 'Papaya2027z',
    });

    expect(Object.keys(parsed).sort()).toEqual(['confirm_password', 'current_password', 'new_password']);
  });

  it('catches a mismatch on the client', () => {
    const issue = errorFor(changePasswordSchema, {
      current_password: 'Mango2026x', new_password: 'Papaya2027z', confirm_password: 'Papaya2028q',
    }, 'confirm_password');

    expect(issue?.message).toBe('Passwords do not match');
  });
});
