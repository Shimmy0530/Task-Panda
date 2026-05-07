// Tiny fetch wrapper that always sends cookies and unwraps JSON.
const base = '';

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
  config: () => api.get('/api/auth/config'),
  login: (password, totp_code) => api.post('/api/auth/login', { password, totp_code }),
  logout: () => api.post('/api/auth/logout')
};

export const tasks = {
  list: (day) => api.get(`/api/tasks${day ? `?day=${day}` : ''}`),
  get: (id) => api.get(`/api/tasks/${id}`),
  create: (t) => api.post('/api/tasks', t),
  update: (id, patch) => api.patch(`/api/tasks/${id}`, patch),
  remove: (id) => api.del(`/api/tasks/${id}`),
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
  process: (id) => api.patch(`/api/capture/${id}`)
};

export const llm = {
  firstAction: (title, notes) => api.post('/api/llm/first-action', { title, notes })
};

// YYYY-MM-DD in the user's local TZ
export function localToday() {
  return new Date().toLocaleDateString('en-CA');
}

export const morning = {
  state: (today) => api.get(`/api/morning/state?today=${today}`),
  complete: (payload) => api.post('/api/morning/complete', payload),
  skip: (today) => api.post(`/api/morning/skip?today=${today}`),
  reset: () => api.post('/api/morning/reset')
};
