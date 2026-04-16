import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authAPI } from '../services/api'
import { Shield, User, Mail, Lock, Eye, EyeOff } from 'lucide-react'

export default function RegisterPage() {
  const navigate               = useNavigate()
  const [form, setForm]        = useState({ username: '', email: '', password: '' })
  const [error, setError]      = useState('')
  const [loading, setLoading]  = useState(false)
  const [showPw, setShowPw]    = useState(false)

  const handle = async e => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await authAPI.register(form)
      navigate('/login')
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="login-bg">
      <div className="login-grid-bg" />
      <div style={{ width: '100%', maxWidth: 400, padding: '0 20px', position: 'relative', zIndex: 1 }} className="fade-in">

        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 52, height: 52,
            background: 'var(--teal-glow)',
            border: '1px solid rgba(0,229,204,0.3)',
            borderRadius: 13,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 14px',
          }}>
            <Shield size={24} color="var(--teal)" />
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-1)' }}>SENTINEL AI</div>
          <div style={{ fontSize: 10, color: 'var(--teal)', fontFamily: 'var(--font-mono)', letterSpacing: '0.2em', marginTop: 4 }}>
            REQUEST ACCESS
          </div>
        </div>

        <div className="card" style={{ borderColor: 'var(--border-bright)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', marginBottom: 20 }}>
            CREATE OPERATOR ACCOUNT
          </div>

          <form onSubmit={handle} style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
            {[
              { key: 'username', label: 'USERNAME',     icon: User,  type: 'text',     ph: 'Choose username' },
              { key: 'email',    label: 'EMAIL',        icon: Mail,  type: 'email',    ph: 'operator@org.com' },
            ].map(({ key, label, icon: Icon, type, ph }) => (
              <div key={key}>
                <label style={{ fontSize: 10, color: 'var(--text-3)', display: 'block', marginBottom: 6, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
                  {label}
                </label>
                <div style={{ position: 'relative' }}>
                  <Icon size={14} color="var(--text-3)" style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                  <input
                    type={type} placeholder={ph}
                    value={form[key]}
                    onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                    required style={{ paddingLeft: 34 }}
                  />
                </div>
              </div>
            ))}

            <div>
              <label style={{ fontSize: 10, color: 'var(--text-3)', display: 'block', marginBottom: 6, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
                PASSWORD
              </label>
              <div style={{ position: 'relative' }}>
                <Lock size={14} color="var(--text-3)" style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
                <input
                  type={showPw ? 'text' : 'password'}
                  placeholder="Create password"
                  value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  required
                  style={{ paddingLeft: 34, paddingRight: 40 }}
                />
                <button type="button" onClick={() => setShowPw(s => !s)} style={{
                  position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', padding: 2,
                }}>
                  {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <div style={{
                padding: '8px 12px',
                background: 'var(--red-dim)',
                border: '1px solid rgba(255,61,90,0.25)',
                borderRadius: 'var(--radius)',
                color: 'var(--red)', fontSize: 12,
                fontFamily: 'var(--font-mono)',
              }}>
                ⚠ {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={loading} style={{ height: 42, fontSize: 13, letterSpacing: '0.05em', marginTop: 2 }}>
              {loading ? <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> CREATING...</> : 'CREATE ACCOUNT'}
            </button>
          </form>

          <div style={{ marginTop: 18, textAlign: 'center', fontSize: 12, color: 'var(--text-3)' }}>
            Have an account?{' '}
            <Link to="/login" style={{ color: 'var(--teal)' }}>Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  )
}