const BASE = import.meta.env.VITE_API_URL ?? ''

export async function apiFetch(path, options = {}) {
  const token = sessionStorage.getItem('cat_token')
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Token ${token}` } : {}),
    ...options.headers,
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (res.status === 401) {
    sessionStorage.clear()
    window.location.href = '/login'
  }
  return res
}
