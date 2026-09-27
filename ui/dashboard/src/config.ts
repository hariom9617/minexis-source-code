/**
 * Single source-of-truth for backend URLs.
 *
 * Override at build time with:
 *   VITE_API_BASE_URL=http://192.168.1.10:8000 npm run dev
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

/** HTTP base URL — used for REST calls */
export const HTTP_BASE = API_BASE;

/** WebSocket URL derived from the HTTP base */
export const WS_LIVE_URL = API_BASE.replace(/^http/, 'ws') + '/ws/live';
