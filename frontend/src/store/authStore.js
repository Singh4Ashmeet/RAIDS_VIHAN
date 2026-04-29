import { create } from 'zustand'
import axios from 'axios'

const rawApiBase = import.meta.env.VITE_API_BASE_URL || ''
const AUTH_API_ROOT = rawApiBase
  ? `${rawApiBase.replace(/\/$/, '')}/api`
  : '/api'

let authMemory = {
  token: null,
  role: null,
  username: null,
  user: null,
}

function unwrapEnvelope(payload) {
  if (payload && typeof payload === 'object' && 'status' in payload && 'data' in payload) {
    return payload.data
  }
  return payload
}

const useAuthStore = create((set, get) => ({
  user: null,
  token: null,
  role: null,
  username: null,
  isAuthenticated: false,
  hasHydrated: false,
  isLoading: false,
  error: null,

  login: async (username, password) => {
    set({ isLoading: true, error: null })
    try {
      const normalizedUsername = username.trim()
      const formData = new FormData()
      formData.append('username', normalizedUsername)
      formData.append('password', password)

      const res = await axios.post(`${AUTH_API_ROOT}/auth/login`, formData)
      const payload = unwrapEnvelope(res.data)
      const { access_token: token, role } = payload

      authMemory = {
        token,
        role,
        username: normalizedUsername,
        user: { username: normalizedUsername, role },
      }
      set({
        token,
        role,
        username: normalizedUsername,
        user: authMemory.user,
        isAuthenticated: true,
        hasHydrated: true,
        isLoading: false,
        error: null,
      })
      return { ok: true, role }
    } catch (err) {
      const message = err.response?.data?.message || err.response?.data?.detail || 'Incorrect username or password'
      set({ isLoading: false, error: message })
      return { ok: false, message }
    }
  },

  logout: (redirect = true) => {
    authMemory = { token: null, role: null, username: null, user: null }
    set({
      user: null,
      token: null,
      role: null,
      username: null,
      isAuthenticated: false,
      hasHydrated: true,
      isLoading: false,
      error: null,
    })
    if (redirect && window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  },

  hydrate: async () => {
    const current = get()
    const token = authMemory.token || current.token
    const rememberedRole = authMemory.role || current.role
    const rememberedUsername = authMemory.username || current.username
    if (!token) {
      set({
        user: null,
        token: null,
        role: null,
        username: null,
        isAuthenticated: false,
        hasHydrated: true,
      })
      return
    }

    set({ isLoading: true })
    try {
      const res = await axios.get(`${AUTH_API_ROOT}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const profile = unwrapEnvelope(res.data)
      const resolvedRole = profile.role || rememberedRole
      const resolvedUsername = profile.username || rememberedUsername
      authMemory = {
        token,
        role: resolvedRole,
        username: resolvedUsername,
        user: profile,
      }
      set({
        token,
        role: resolvedRole,
        username: resolvedUsername,
        user: profile,
        isAuthenticated: true,
        hasHydrated: true,
        isLoading: false,
        error: null,
      })
    } catch {
      authMemory = { token: null, role: null, username: null, user: null }
      set({
        user: null,
        token: null,
        role: null,
        username: null,
        isAuthenticated: false,
        hasHydrated: true,
        isLoading: false,
      })
    }
  },

  isAdmin: () => get().role === 'admin',
  isUser: () => get().role === 'user' || get().role === 'admin',
  isAuthed: () => !!get().token && get().isAuthenticated,
}))

export default useAuthStore
