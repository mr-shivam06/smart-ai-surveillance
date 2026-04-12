// src/pages/LoginPage.jsx
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Shield, Eye, EyeOff } from 'lucide-react'

export default function LoginPage() {
  const { login }              = useAuth()
  const navigate               = useNavigate()
  const [form, setForm]        = useState({ username:'', password:'' })
  const [error, setError]      = useState('')
  const [loading, setLoading]  = useState(false)
  const [showPw, setShowPw]    = useState(false)

  const handle = async e => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      await login(form.username, form.password)
      navigate('/')
    } catch(err) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally { setLoading(false) }
  }

  return (
    <div style={{
      minHeight:'100vh', display:'flex',
      alignItems:'center', justifyContent:'center',
      background:'var(--bg-900)',
    }}>
      <div style={{ width:'100%', maxWidth:400, padding:'0 20px' }}>

        {/* Logo */}
        <div style={{ textAlign:'center', marginBottom:32 }}>
          <Shield size={40} color="var(--teal)" style={{ marginBottom:12 }}/>
          <h1 style={{ fontSize:22, fontWeight:700, color:'var(--text-1)' }}>
            Smart AI Surveillance
          </h1>
          <p style={{ color:'var(--text-3)', fontSize:13, marginTop:4 }}>
            Sign in to your dashboard
          </p>
        </div>

        <div className="card">
          <form onSubmit={handle} style={{ display:'flex', flexDirection:'column', gap:16 }}>
            <div>
              <label style={{ fontSize:12, color:'var(--text-3)', display:'block', marginBottom:6 }}>
                Username
              </label>
              <input
                type="text"
                placeholder="Enter username"
                value={form.username}
                onChange={e => setForm(f=>({...f, username:e.target.value}))}
                required
                style={{ width:'100%' }}
              />
            </div>

            <div>
              <label style={{ fontSize:12, color:'var(--text-3)', display:'block', marginBottom:6 }}>
                Password
              </label>
              <div style={{ position:'relative' }}>
                <input
                  type={showPw ? 'text' : 'password'}
                  placeholder="Enter password"
                  value={form.password}
                  onChange={e => setForm(f=>({...f, password:e.target.value}))}
                  required
                  style={{ width:'100%', paddingRight:40 }}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(s=>!s)}
                  style={{
                    position:'absolute', right:10, top:'50%',
                    transform:'translateY(-50%)',
                    background:'none', border:'none',
                    color:'var(--text-3)', padding:0,
                  }}
                >
                  {showPw ? <EyeOff size={16}/> : <Eye size={16}/>}
                </button>
              </div>
            </div>

            {error && (
              <div style={{
                padding:'10px 14px', background:'rgba(239,68,68,0.12)',
                border:'1px solid rgba(239,68,68,0.3)',
                borderRadius:'var(--radius)', color:'var(--red)', fontSize:13,
              }}>
                {error}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{ justifyContent:'center', padding:'10px' }}
            >
              {loading ? <><div className="spinner" style={{width:16,height:16,borderWidth:2}}/> Signing in...</> : 'Sign In'}
            </button>
          </form>

          <p style={{ textAlign:'center', marginTop:16, fontSize:13, color:'var(--text-3)' }}>
            No account?{' '}
            <Link to="/register" style={{ color:'var(--teal)', fontWeight:500 }}>
              Register
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}