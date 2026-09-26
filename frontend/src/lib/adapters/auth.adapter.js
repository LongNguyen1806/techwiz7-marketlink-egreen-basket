/**
 * The `Me` object, Pass 4B §3.1. MeReadSerializer always sends every field, with `role` as the
 * code string and `display_name` already resolved per role, so this is a straight read of the
 * contract rather than a guess at the shape.
 */
export function adaptMe(raw) {
  return {
    id: raw.id,
    email: raw.email,
    role: raw.role,
    display_name: raw.display_name,
    farmer_status: raw.farmer_status ?? null,
  };
}
