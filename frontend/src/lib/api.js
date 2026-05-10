// Tiny fetch wrapper that always sends cookies and unwraps JSON.
const base = '';

// YYYY-MM-DD in the user's local TZ
export function localToday() {
  return new Date().toLocaleDateString('en-CA');
}

// Returns null when valid, an error string otherwise.
export function validateNewPassword(pw, confirm) {
  if (!pw || pw.length < 12) return 'password must be at least 12 chars';
  if (pw !== confirm) return 'passwords do not match';
  return null;
}

async function request(path, opts = {}) {
  const res = await fetch(`${base}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg = data?.detail || data?.message || res.statusText;
    throw new Error(msg);
  }
  return data;
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: 'POST', body: JSON.stringify(body || {}) }),
  patch: (p, body) => request(p, { method: 'PATCH', body: JSON.stringify(body || {}) }),
  del: (p) => request(p, { method: 'DELETE' })
};

export const auth = {
  me: () => api.get('/api/auth/me'),
  setupRequired: () => api.get('/api/auth/setup-required'),
  setup: (username, password) => api.post('/api/auth/setup', { username, password }),
  login: (username, password, totp_code) =>
    api.post('/api/auth/login', { username, password, totp_code }),
  logout: () => api.post('/api/auth/logout'),
  changePassword: (current_password, new_password) =>
    api.post('/api/auth/change-password', { current_password, new_password }),
  totpSetup: () => api.post('/api/auth/totp/setup'),
  totpConfirm: (code) => api.post('/api/auth/totp/confirm', { code }),
  totpDisable: (password) => api.post('/api/auth/totp/disable', { password })
};

export const admin = {
  users: () => api.get('/api/admin/users'),
  createUser: (u) => api.post('/api/admin/users', u),
  resetPassword: (id, new_password) =>
    api.post(`/api/admin/users/${id}/reset-password`, { new_password }),
  disable: (id) => api.post(`/api/admin/users/${id}/disable`),
  enable: (id) => api.post(`/api/admin/users/${id}/enable`)
};

export const tasks = {
  list: (day) => api.get(`/api/tasks?day=${day || localToday()}`),
  get: (id) => api.get(`/api/tasks/${id}`),
  create: (t) => api.post('/api/tasks', t),
  update: (id, patch) => api.patch(`/api/tasks/${id}`, patch),
  remove: (id) => api.del(`/api/tasks/${id}`),
  copy: (id) => api.post(`/api/tasks/${id}/copy`),
  backlog: () => api.get('/api/tasks/backlog'),
  appendDictation: (id, outline, transcript) =>
    api.post(`/api/tasks/${id}/dictation`, { outline, transcript })
};

export const sessions = {
  start: (task_id, secs) =>
    api.post('/api/sessions/start', { task_id, duration_planned_seconds: secs }),
  end: (id, completed = true) => api.post(`/api/sessions/${id}/end?completed=${completed}`),
  today: () => api.get('/api/sessions/today'),
  week: () => api.get('/api/sessions/week')
};

export const captures = {
  list: () => api.get('/api/capture'),
  create: (content) => api.post('/api/capture', { content }),
  process: (id) => api.patch(`/api/capture/${id}`),
  convert: (id, target) => api.post(`/api/capture/${id}/convert`, { target })
};

export const llm = {
  firstAction: (title, notes) => api.post('/api/llm/first-action', { title, notes }),
  subtasks: (task_id) => api.post('/api/llm/subtasks', { task_id }),
  weeklyReview: (today) => api.post(`/api/llm/weekly-review?today=${today || localToday()}`)
};

export const morning = {
  state: (today) => api.get(`/api/morning/state?today=${today}`),
  complete: (payload) => api.post('/api/morning/complete', payload),
  skip: (today) => api.post(`/api/morning/skip?today=${today}`),
  reset: () => api.post('/api/morning/reset')
};

export const settings = {
  get: () => api.get('/api/settings'),
  update: (patch) => api.patch('/api/settings', patch)
};
