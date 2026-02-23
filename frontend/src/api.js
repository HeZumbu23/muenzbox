const BASE = '/api'

async function request(path, options = {}) {
  const resp = await fetch(BASE + path, {
    signal: AbortSignal.timeout(10000),
    headers: {
      'Content-Type': 'application/json',
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      ...options.headers,
    },
    ...options,
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    const error = new Error(err.detail || 'Fehler')
    error.status = resp.status
    throw error
  }
  if (resp.status === 204) return null
  return resp.json()
}

// --- Public ---
export const getChildren = () => request('/children')

export const verifyPin = (childId, pin) =>
  request(`/children/${childId}/verify-pin`, {
    method: 'POST',
    body: JSON.stringify({ pin }),
  })

// --- Child (requires token) ---
export const getChildStatus = (childId, token) =>
  request(`/children/${childId}/status`, { token })

export const getActiveSession = (childId, token) =>
  request(`/children/${childId}/active-session`, { token })

export const startSession = (childId, type, coins, token) =>
  request('/sessions', {
    method: 'POST',
    token,
    body: JSON.stringify({ child_id: childId, type, coins }),
  })

export const endSession = (sessionId, token) =>
  request(`/sessions/${sessionId}/end`, { method: 'POST', token })

// --- Admin ---
export const adminVerify = (pin) =>
  request('/admin/verify', {
    method: 'POST',
    body: JSON.stringify({ pin }),
  })

export const adminGetChildren = (token) =>
  request('/admin/children', { token })

export const adminCreateChild = (data, token) =>
  request('/admin/children', {
    method: 'POST',
    token,
    body: JSON.stringify(data),
  })

export const adminUpdateChild = (childId, data, token) =>
  request(`/admin/children/${childId}`, {
    method: 'PUT',
    token,
    body: JSON.stringify(data),
  })

export const adminDeleteChild = (childId, token) =>
  request(`/admin/children/${childId}`, { method: 'DELETE', token })

export const adminAdjustCoins = (childId, type, delta, reason, token) =>
  request(`/admin/children/${childId}/adjust-coins`, {
    method: 'POST',
    token,
    body: JSON.stringify({ type, delta, reason }),
  })

export const adminGetSessions = (token) =>
  request('/admin/sessions', { token })

export const adminCancelSession = (sessionId, token) =>
  request(`/admin/sessions/${sessionId}/cancel`, { method: 'POST', token })

export const adminGetCoinLog = (childId, token) =>
  request(`/admin/coin-log${childId ? `?child_id=${childId}` : ''}`, { token })

export const adminGetMockStatus = (token) =>
  request('/admin/mock-status', { token })
