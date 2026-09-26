/**
 * Notification, exactly as `serialize_notification` builds it (Pass 4B §4.6). The WebSocket frame
 * carries the same shape as NO-01, so one reader covers both.
 *
 * Nothing is invented here: a field the backend stops sending should surface as an empty cell, not as
 * a title guessed from the type.
 */
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
