import { apiFetch } from './client.js'

export const login = (username, password) =>
  apiFetch('/user_auth/login/', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })

export const signup = (username, email, password) =>
  apiFetch('/user_auth/signup/', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
  })

export const logout = () =>
  apiFetch('/user_auth/logout/', { method: 'POST' })

export const healthCheck = () =>
  apiFetch('/user_auth/health/')
