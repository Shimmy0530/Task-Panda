import { writable } from 'svelte/store';

// Populated by +layout.svelte after auth.me() succeeds; null while unauthenticated.
// Shape: { id, username, is_admin, totp_enrolled, last_ritual_date }
export const user = writable(null);
