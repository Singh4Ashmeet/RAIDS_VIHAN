import { create } from 'zustand'
import axios from 'axios'

const rawApiBase = import.meta.env.VITE_API_BASE_URL || ''
const AUTH_API_ROOT = rawApiBase
  ? `${rawApiBase.replace(/\/$/, '')}/api`
  : '/api'

function clearAuthStorage() {
  localStorage.removeItem('raid_token')
  localStorage.removeItem('raid_role')
  localStorage.removeItem('raid_username')
  localStorage.removeItem('raid_name')
}

const initialToken = localStorage.getItem('raid_token')
const initialRole = localStorage.getItem('raid_role')
const initialUsername = localStorage.getItem('raid_username')

const useAuthStore = create((set, get) => ({
  user:      initialUsername ? { username: initialUsername, role: initialRole } : null,
  token:     initialToken,
  role:      initialRole,
  username:  initialUsername,
  isAuthenticated: !!initialToken,
  hasHydrated: false,
  isLoading: false,
  error:     null,

  login: async (username, password) => {
    set({ isLoading: true, error: null })
    try {
      const formData = new FormData()
      formData.append('username', username)
      formData.append('password', password)

      const res = await axios.post(`${AUTH_API_ROOT}/auth/login`, formData)
      const { access_token: token, role } = res.data

      localStorage.setItem('raid_token', token)
      localStorage.setItem('raid_role',  role)
      localStorage.setItem('raid_username', username)
      set({
        token,
        role,
        username,
        user: { username, role },
        isAuthenticated: true,
        hasHydrated: true,
        isLoading: false,
        error: null,
      })
      return { ok: true, role }
    } catch (err) {
      const message = err.response?.data?.detail || 'Incorrect username or password'
      set({ isLoading: false, error: message })
      return { ok: false, message }
    }
  },

  logout: (redirect = true) => {
    clearAuthStorage()
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
    const token = localStorage.getItem('raid_token')
    const role  = localStorage.getItem('raid_role')
    const username = localStorage.getItem('raid_username')
    if (!token) {
      clearAuthStorage()
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
      const profile = res.data
      const resolvedRole = profile.role || role
      const resolvedUsername = profile.username || username
      localStorage.setItem('raid_role', resolvedRole)
      localStorage.setItem('raid_username', resolvedUsername)
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
      clearAuthStorage()
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
  isUser:  () => get().role === 'user' || get().role === 'admin',
  isAuthed:() => !!get().token && get().isAuthenticated,
}))

export default useAuthStore
