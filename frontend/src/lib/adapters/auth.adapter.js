
export function adaptMe(raw) {
  return {
    id: raw.id,
    email: raw.email,
    role: raw.role,
    display_name: raw.display_name,
    farmer_status: raw.farmer_status ?? null,
  };
}
