/**
 * Runtime API configuration for the Policy & Leave Concierge.
 *
 * The base URL comes from VITE_API_BASE_URL. When it is missing the app falls
 * back to mock data so the UI is fully usable before the backend exists.
 *
 * Auth: handled entirely by the backend. Requests are sent with credentials
 * so the session cookie / gateway-injected bearer token travels server-side.
 * No token is ever stored, entered or held in the client.
 */

export const API_BASE_URL: string = (import.meta.env["VITE_API_BASE_URL"] ?? "").replace(/\/$/, "");

export const isApiConfigured = () => API_BASE_URL.length > 0;
