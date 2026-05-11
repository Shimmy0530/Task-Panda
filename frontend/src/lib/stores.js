import { writable } from 'svelte/store';

// Populated by +layout.svelte after auth.me() succeeds; null while unauthenticated.
// Shape: { id, username, is_admin, totp_enrolled, last_ritual_date, welcomed_at }
export const user = writable(null);
