import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useState, useEffect } from 'react'
import { alertAPI } from '../services/api'
import {
  LayoutDashboard, Camera, Bell, Car, Activity,
  LogOut, Shield, ChevronLeft, ChevronRight
} from 'lucide-react'

const NAV = [
  { to: '/',         icon: LayoutDashboard, label: 'Dashboard'  },
  { to: '/cameras',  icon: Camera,          label: 'Cameras'    },
  { to: '/tracking', icon: Activity,        label: 'Tracking'   },
  { to: '/alerts',   icon: Bell,            label: 'Alerts'     },
  { to: '/vehicles', icon: Car,             label: 'Vehicles'   },
]

export default function Layout() {
  const { user, logout }        = useAuth()
  const navigate                = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [alertCount, setAlertCount] = useState(0)

  useEffect(() => {
    const fetch = () =>
      alertAPI.count().then(r => setAlertCount(r.data.unacknowledged)).catch(() => {})
    fetch()
    const id = setInterval(fetch, 5000)
    return () => clearInterval(id)
  }, [])

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div style={{ display:'flex', height:'100vh', overflow:'hidden' }}>

      {/* ── Sidebar ── */}
      <aside style={{
        width: collapsed ? 60 : 220,
        background: 'var(--bg-800)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s',
        flexShrink: 0,
        overflow: 'hidden',
      }}>

        {/* Logo */}
        <div style={{
          padding: '18px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          minHeight: 60,
        }}>
          <Shield size={22} color="var(--teal)" style={{ flexShrink:0 }} />
          {!collapsed && (
            <span style={{ fontWeight:700, fontSize:13, color:'var(--teal)', whiteSpace:'nowrap' }}>
              AI SURVEILLANCE
            </span>
          )}
        </div>

        {/* Nav links */}
        <nav style={{ flex:1, padding:'12px 8px', display:'flex', flexDirection:'column', gap:2 }}>
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '9px 10px',
                borderRadius: 'var(--radius)',
                color: isActive ? 'var(--teal)' : 'var(--text-2)',
                background: isActive ? 'rgba(13,217,197,0.08)' : 'transparent',
                fontWeight: isActive ? 600 : 400,
                fontSize: 13,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                transition: 'all 0.15s',
                position: 'relative',
              })}
            >
              <Icon size={17} style={{ flexShrink:0 }} />
              {!collapsed && <span>{label}</span>}
              {/* Alert badge on Alerts link */}
              {label === 'Alerts' && alertCount > 0 && (
                <span style={{
                  marginLeft:'auto',
                  background:'var(--red)',
                  color:'white',
                  borderRadius:10,
                  padding:'1px 6px',
                  fontSize:10,
                  fontWeight:700,
                  display: collapsed ? 'none' : 'block',
                }}>
                  {alertCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="btn btn-ghost"
          style={{ margin:'8px', justifyContent:'center', padding:'8px' }}
        >
          {collapsed ? <ChevronRight size={16}/> : <ChevronLeft size={16}/>}
        </button>

        {/* User + logout */}
        <div style={{
          padding:'12px 8px',
          borderTop:'1px solid var(--border)',
        }}>
          {!collapsed && (
            <div style={{ padding:'8px 10px', marginBottom:4 }}>
              <div style={{ fontSize:12, fontWeight:600, color:'var(--text-1)' }}>
                {user?.username}
              </div>
              <div style={{ fontSize:11, color:'var(--text-3)' }}>
                {user?.email}
              </div>
            </div>
          )}
          <button
            onClick={handleLogout}
            className="btn btn-ghost"
            style={{ width:'100%', justifyContent: collapsed ? 'center' : 'flex-start' }}
          >
            <LogOut size={15}/>
            {!collapsed && 'Logout'}
          </button>
        </div>
      </aside>

      {/* ── Main content ── */}
      <main style={{
        flex: 1,
        overflow: 'auto',
        background: 'var(--bg-900)',
        padding: '28px 32px',
      }}>
        <Outlet />
      </main>
    </div>
  )
}