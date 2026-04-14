import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authAPI } from '../services/api'
import { Shield } from 'lucide-react'

export default function RegisterPage() {
  const navigate = useNavigate()

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: ''
  })

  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handle = async (e) => {
    e.preventDefault()
    setError('')

    // ✅ Basic validation
    if (!form.username || !form.email || !form.password) {
      setError('All fields are required')
      return
    }

    if (form.password.length < 4) {
      setError('Password must be at least 4 characters')
      return
    }

    setLoading(true)

    try {
      await authAPI.register(form)

      // ✅ Success → redirect
      navigate('/login')

    } catch (err) {
      console.error(err)

      setError(
        err.response?.data?.detail ||
        err.message ||
        'Registration failed'
      )

    } finally {
      setLoading(false)
    }
  }

  const f = (key, val) => {
    setForm(prev => ({ ...prev, [key]: val }))
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-900)',
    }}>
      <div style={{ width: '100%', maxWidth: 400, padding: '0 20px' }}>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <Shield size={40} color="var(--teal)" style={{ marginBottom: 12 }} />
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>Create Account</h1>
          <p style={{ color: 'var(--text-3)', fontSize: 13, marginTop: 4 }}>
            Register to access the dashboard
          </p>
        </div>

        <div className="card">
          <form
            onSubmit={handle}
            style={{ display: 'flex', flexDirection: 'column', gap: 16 }}
          >

            {/* Inputs */}
            {[
              { key: 'username', label: 'Username', type: 'text', placeholder: 'Choose a username' },
              { key: 'email',    label: 'Email',    type: 'email', placeholder: 'Your email address' },
              { key: 'password', label: 'Password', type: 'password', placeholder: 'Choose a password' },
            ].map(({ key, label, type, placeholder }) => (
              <div key={key}>
                <label style={{
                  fontSize: 12,
                  color: 'var(--text-3)',
                  display: 'block',
                  marginBottom: 6
                }}>
                  {label}
                </label>

                <input
                  type={type}
                  placeholder={placeholder}
                  value={form[key]}
                  onChange={e => f(key, e.target.value)}
                  disabled={loading}   // ✅ prevent editing while submitting
                  required
                  style={{ width: '100%' }}
                />
              </div>
            ))}

            {/* Error */}
            {error && (
              <div style={{
                padding: '10px 14px',
                background: 'rgba(239,68,68,0.12)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 'var(--radius)',
                color: 'var(--red)',
                fontSize: 13,
              }}>
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{ justifyContent: 'center', padding: '10px' }}
            >
              {loading ? 'Creating account...' : 'Create Account'}
            </button>
          </form>

          {/* Footer */}
          <p style={{
            textAlign: 'center',
            marginTop: 16,
            fontSize: 13,
            color: 'var(--text-3)'
          }}>
            Already have an account?{' '}
            <Link to="/login" style={{ color: 'var(--teal)', fontWeight: 500 }}>
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}