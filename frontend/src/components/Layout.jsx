import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useState, useEffect } from 'react'
import { alertAPI, healthAPI } from '../services/api'
import {
  LayoutDashboard, Camera, Bell, Car, Activity,
  LogOut, Shield, ChevronLeft, ChevronRight, Radio
} from 'lucide-react'

const NAV = [
  { to: '/',         icon: LayoutDashboard, label: 'Dashboard',  key: 'dashboard' },
  { to: '/cameras',  icon: Camera,          label: 'Cameras',    key: 'cameras'   },
  { to: '/tracking', icon: Activity,        label: 'Tracking',   key: 'tracking'  },
  { to: '/alerts',   icon: Bell,            label: 'Alerts',     key: 'alerts'    },
  { to: '/vehicles', icon: Car,             label: 'Vehicles',   key: 'vehicles'  },
]

export default function Layout() {
  const { user, logout }              = useAuth()
  const navigate                      = useNavigate()
  const [collapsed, setCollapsed]     = useState(false)
  const [alertCount, setAlertCount]   = useState(0)
  const [sysOnline, setSysOnline]     = useState(true)
  const [streamCount, setStreamCount] = useState(0)

  useEffect(() => {
    const poll = async () => {
      try {
        const [ac, hc] = await Promise.all([
          alertAPI.count(),
          healthAPI.check(),
        ])
        setAlertCount(ac.data.unacknowledged)
        setSysOnline(true)
        setStreamCount(hc.data.streaming_cams?.length ?? 0)
      } catch {
        setSysOnline(false)
      }
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="app-shell">

      {/* ── Sidebar ── */}
      <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>

        {/* Logo */}
        <div className="sidebar-logo">
          <Shield size={20} color="var(--teal)" style={{ flexShrink: 0 }} />
          {!collapsed && (
            <div className="sidebar-logo-text">
              SENTINEL AI
              <span>Surveillance System</span>
            </div>
          )}
        </div>

        {/* System status pill */}
        {!collapsed && (
          <div style={{
            margin: '10px 10px 0',
            padding: '6px 10px',
            background: sysOnline ? 'rgba(0,230,118,0.07)' : 'rgba(255,61,90,0.07)',
            border: `1px solid ${sysOnline ? 'rgba(0,230,118,0.18)' : 'rgba(255,61,90,0.18)'}`,
            borderRadius: 'var(--radius)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
            color: sysOnline ? 'var(--green)' : 'var(--red)',
          }}>
            <div className={sysOnline ? 'live-dot' : ''} style={!sysOnline ? {
              width: 8, height: 8, borderRadius: '50%',
              background: 'var(--red)', flexShrink: 0,
            } : { flexShrink: 0 }} />
            {sysOnline ? `ONLINE · ${streamCount} STREAM${streamCount !== 1 ? 'S' : ''}` : 'BACKEND OFFLINE'}
          </div>
        )}

        {/* Nav links */}
        <nav className="sidebar-nav" style={{ marginTop: collapsed ? 0 : 8 }}>
          {NAV.map(({ to, icon: Icon, label, key }) => (
            <NavLink
              key={key}
              to={to}
              end={to === '/'}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              <Icon size={16} style={{ flexShrink: 0 }} />
              {!collapsed && <span>{label}</span>}
              {key === 'alerts' && alertCount > 0 && !collapsed && (
                <span className="nav-badge">{alertCount}</span>
              )}
              {key === 'alerts' && alertCount > 0 && collapsed && (
                <span style={{
                  position: 'absolute', top: 5, right: 5,
                  width: 7, height: 7, borderRadius: '50%',
                  background: 'var(--red)',
                }} />
              )}
            </NavLink>
          ))}
        </nav>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="btn btn-ghost btn-sm"
          style={{ margin: '6px 8px', justifyContent: 'center', gap: 0 }}
        >
          {collapsed ? <ChevronRight size={15} /> : <><ChevronLeft size={15} /><span style={{ marginLeft: 6, fontSize: 11 }}>Collapse</span></>}
        </button>

        {/* User */}
        <div className="sidebar-footer">
          {!collapsed && (
            <div className="sidebar-user" style={{ marginBottom: 6 }}>
              <div className="sidebar-user-name">{user?.username}</div>
              <div className="sidebar-user-role">OPERATOR</div>
            </div>
          )}
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="btn btn-ghost btn-sm"
            style={{ width: '100%', justifyContent: collapsed ? 'center' : 'flex-start' }}
          >
            <LogOut size={14} />
            {!collapsed && 'Sign Out'}
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}