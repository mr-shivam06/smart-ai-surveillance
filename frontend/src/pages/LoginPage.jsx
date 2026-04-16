import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Shield, Eye, EyeOff, Lock, User } from 'lucide-react'

export default function LoginPage() {
  const { login }              = useAuth()
  const navigate               = useNavigate()
  const [form, setForm]        = useState({ username: '', password: '' })
  const [error, setError]      = useState('')
  const [loading, setLoading]  = useState(false)
  const [showPw, setShowPw]    = useState(false)

  const handle = async e => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await login(form.username, form.password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials')
    } finally { setLoading(false) }
  }

  return (
    <div className="login-bg">
      <div className="login-grid-bg" />

      <div style={{ width: '100%', maxWidth: 400, padding: '0 20px', position: 'relative', zIndex: 1 }} className="fade-in">

        {/* Logo block */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{
            width: 56, height: 56,
            background: 'var(--teal-glow)',
            border: '1px solid rgba(0,229,204,0.3)',
            borderRadius: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: 'var(--glow-teal)',
          }}>
            <Shield size={26} color="var(--teal)" />
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-1)', letterSpacing: -0.5 }}>
            SENTINEL AI
          </div>
          <div style={{
            fontSize: 10, color: 'var(--teal)', fontFamily: 'var(--font-mono)',
            letterSpacing: '0.2em', marginTop: 4,
          }}>
            SURVEILLANCE SYSTEM
          </div>
        </div>

        {/* Card */}
        <div className="card" style={{ borderColor: 'var(--border-bright)' }}>
          <div style={{
            fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)',
            letterSpacing: '0.1em', marginBottom: 20,
          }}>
            OPERATOR AUTHENTICATION
          </div>

          <form onSubmit={handle} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {/* Username */}
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 6, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
                USERNAME
              </label>
              <div style={{ position: 'relative' }}>
                <User size={14} color="var(--text-3)" style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                <input
                  type="text"
                  placeholder="Enter username"
                  value={form.username}
                  onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                  required
                  style={{ paddingLeft: 34 }}
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-3)', display: 'block', marginBottom: 6, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
                PASSWORD
              </label>
              <div style={{ position: 'relative' }}>
                <Lock size={14} color="var(--text-3)" style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                <input
                  type={showPw ? 'text' : 'password'}
                  placeholder="Enter password"
                  value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  required
                  style={{ paddingLeft: 34, paddingRight: 40 }}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(s => !s)}
                  style={{
                    position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', color: 'var(--text-3)', padding: 2, cursor: 'pointer',
                  }}
                >
                  {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <div style={{
                padding: '9px 12px',
                background: 'var(--red-dim)',
                border: '1px solid rgba(255,61,90,0.25)',
                borderRadius: 'var(--radius)',
                color: 'var(--red)', fontSize: 12,
                fontFamily: 'var(--font-mono)',
              }}>
                ⚠ {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={loading} style={{ marginTop: 4, height: 42, fontSize: 13, letterSpacing: '0.05em' }}>
              {loading ? <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> AUTHENTICATING...</> : 'SIGN IN'}
            </button>
          </form>

          <div style={{ marginTop: 18, textAlign: 'center', fontSize: 12, color: 'var(--text-3)' }}>
            No account?{' '}
            <Link to="/register" style={{ color: 'var(--teal)' }}>Register access</Link>
          </div>
        </div>
      </div>
    </div>
  )
}