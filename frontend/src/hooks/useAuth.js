import { useCallback } from 'react'
import { login as apiLogin, logout as apiLogout } from '../api/auth.js'

export function useAuth() {
  const getToken    = () => sessionStorage.getItem('cat_token')
  const getUsername = () => sessionStorage.getItem('cat_username') || 'OPERATOR'
  const isAuthenticated = () => !!getToken()

  const login = useCallback(async (username, password) => {
    const res  = await apiLogin(username, password)
    const data = await res.json()
    if (res.ok && data.token) {
      sessionStorage.setItem('cat_token',    data.token)
      sessionStorage.setItem('cat_username', username)
      return { ok: true }
    }
    return { ok: false, data }
  }, [])

  const logout = useCallback(async () => {
    try { await apiLogout() } catch (_) {}
    sessionStorage.clear()
    window.location.href = '/login'
  }, [])

  return { token: getToken(), username: getUsername(), isAuthenticated, login, logout }
}
