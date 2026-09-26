

function resolveWsUrl(value) {
  if (/^wss?:\/\//.test(value)) return value;
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${scheme}://${window.location.host}${value}`;
}

export const env = {
  API_BASE_URL: import.meta.env.VITE_API_URL || '/api',
  WS_BASE_URL: resolveWsUrl(import.meta.env.VITE_WS_URL || '/ws'),
};
