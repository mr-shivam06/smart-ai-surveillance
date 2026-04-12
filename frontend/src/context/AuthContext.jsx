import { createContext, useContext, useState, useEffect } from 'react'
import { authAPI } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // ── Check auth on app load ───────────────────────────
  useEffect(() => {
    const token = localStorage.getItem('token')

    if (token) {
      authAPI.me()
        .then(res => {
          setUser(res.data)
        })
        .catch(() => {
          // token invalid → clear storage
          localStorage.removeItem('token')
          localStorage.removeItem('username')
          setUser(null)
        })
        .finally(() => {
          setLoading(false)
        })
    } else {
      setLoading(false)
    }
  }, [])

  // ── Login ────────────────────────────────────────────
  const login = async (username, password) => {
    try {
      // ✅ FIXED: pass username, password (not object)
      const res = await authAPI.login(username, password)

      // store token
      localStorage.setItem('token', res.data.access_token)

      // fetch user
      const me = await authAPI.me()
      setUser(me.data)

      // optional: store username
      localStorage.setItem('username', me.data.username)

      return me.data

    } catch (err) {
      console.error('Login error:', err)
      throw err
    }
  }

  // ── Logout ───────────────────────────────────────────
  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// ── Hook ──────────────────────────────────────────────
export const useAuth = () => useContext(AuthContext)