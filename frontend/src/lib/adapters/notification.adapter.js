
export function adaptNotification(raw) {
  return {
    id: raw.id,
    type: raw.type,
    title: raw.title,
    message: raw.message,
    target_url: raw.target_url ?? null,
    is_read: Boolean(raw.is_read),
    read_at: raw.read_at ?? null,
    created_at: raw.created_at,
  };
}
