import { useState, useEffect, useRef } from 'react'
import { healthAPI, alertAPI, cameraAPI, trackingAPI } from '../services/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, AreaChart, Area } from 'recharts'
import {
  Shield, Camera, Bell, Activity, AlertTriangle,
  Video, RefreshCw, Cpu, Radio, Users, Car, Zap
} from 'lucide-react'
import { Link } from 'react-router-dom'

const SEV_ACCENT = {
  CRITICAL: { color: 'var(--red)',    cls: 'critical' },
  HIGH:     { color: 'var(--orange)', cls: 'high'     },
  MEDIUM:   { color: 'var(--yellow)', cls: 'medium'   },
  INFO:     { color: 'var(--cyan)',   cls: 'info'      },
}

const BAR_COLORS = [
  'var(--red)','var(--orange)','var(--yellow)',
  'var(--teal)','var(--cyan)','var(--purple)',
]

function useInterval(fn, ms) {
  const cb = useRef(fn)
  useEffect(() => { cb.current = fn }, [fn])
  useEffect(() => {
    const id = setInterval(() => cb.current(), ms)
    return () => clearInterval(id)
  }, [ms])
}

export default function Dashboard() {
  const [health,   setHealth]   = useState(null)
  const [alerts,   setAlerts]   = useState([])
  const [cameras,  setCameras]  = useState([])
  const [tracking, setTracking] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [fpsHistory, setFpsHistory] = useState([])

  const fetchAll = async (quiet = false) => {
    if (!quiet) setLoading(true)
    try {
      const [h, a, c, t] = await Promise.all([
        healthAPI.check(),
        alertAPI.list({ limit: 25 }),
        cameraAPI.list(),
        trackingAPI.status(),
      ])
      setHealth(h.data)
      setAlerts(a.data)
      setCameras(c.data)
      setTracking(t.data)
      setLastUpdate(new Date())
      // Build mini sparkline of streaming cam count over time
      setFpsHistory(prev => {
        const next = [...prev, { t: Date.now(), v: h.data.streaming_cams?.length ?? 0 }]
        return next.slice(-20)
      })
    } catch(e) { console.error(e) }
    finally { if (!quiet) setLoading(false) }
  }

  useEffect(() => { fetchAll() }, [])
  useInterval(() => fetchAll(true), 7000)

  // Chart data
  const typeCounts = alerts.reduce((acc, a) => {
    const k = a.type.replace(/_DETECTED$/, '').replace(/_/g, ' ')
    acc[k] = (acc[k] || 0) + 1
    return acc
  }, {})
  const chartData = Object.entries(typeCounts)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)

  const unacked    = alerts.filter(a => !a.acknowledged).length
  const activeCams = cameras.filter(c => c.is_active).length
  const streaming  = health?.streaming_cams?.length ?? 0
  const recentAlerts = alerts.slice(0, 6)

  if (loading) return (
    <div className="loading-screen">
      <div className="spinner" />
      INITIALIZING DASHBOARD...
    </div>
  )

  return (
    <div className="fade-in">

      {/* ── Page header ── */}
      <div className="page-header">
        <div>
          <div className="page-title">Operations Dashboard</div>
          <div className="page-sub">
            {lastUpdate
              ? `LAST SYNC ${lastUpdate.toLocaleTimeString()}`
              : 'LIVE MONITORING'}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {unacked > 0 && (
            <Link to="/alerts" style={{ textDecoration: 'none' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '7px 14px',
                background: 'var(--red-dim)',
                border: '1px solid rgba(255,61,90,0.3)',
                borderRadius: 'var(--radius)',
                fontSize: 12, color: 'var(--red)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 700,
                animation: 'pulse-badge 2s ease infinite',
              }}>
                <Zap size={13} />
                {unacked} UNACKED ALERT{unacked !== 1 ? 'S' : ''}
              </div>
            </Link>
          )}
          <button className="btn btn-ghost btn-sm" onClick={() => fetchAll()}>
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      {/* ── Stat cards ── */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        {[
          {
            label: 'Active Cameras',
            value: activeCams,
            sub: `${streaming} streaming live`,
            icon: Camera,
            color: 'var(--teal)',
            accent: streaming > 0,
          },
          {
            label: 'Tracked IDs',
            value: health?.global_ids ?? 0,
            sub: `${health?.cross_cam ?? 0} cross-camera`,
            icon: Users,
            color: 'var(--cyan)',
          },
          {
            label: 'Unacked Alerts',
            value: unacked,
            sub: `${alerts.length} total today`,
            icon: Bell,
            color: unacked > 0 ? 'var(--red)' : 'var(--green)',
            urgent: unacked > 0,
          },
          {
            label: 'ReID Backend',
            value: tracking?.reid_backend ?? '—',
            sub: `${tracking?.cross_cam_matches ?? 0} matches`,
            icon: Cpu,
            color: 'var(--purple)',
          },
        ].map(({ label, value, sub, icon: Icon, color, urgent, accent }) => (
          <div key={label} className="stat-card" style={{
            borderColor: urgent ? 'rgba(255,61,90,0.35)' : accent ? 'rgba(0,229,204,0.25)' : undefined,
          }}>
            <div className="sc-label">
              {label}
              <Icon size={14} color={color} />
            </div>
            <div className="sc-value" style={{ color }}>{value}</div>
            <div className="sc-sub">{sub}</div>
          </div>
        ))}
      </div>

      {/* ── Middle row: chart + recent alerts ── */}
      <div className="grid-2" style={{ marginBottom: 24 }}>

        {/* Alert breakdown chart */}
        <div className="card">
          <div className="card-header">
            <Activity size={13} color="var(--teal)" />
            Alert Breakdown
          </div>
          {chartData.length === 0 ? (
            <div className="empty-state" style={{ padding: '36px 0' }}>
              <Bell size={28} />
              <p>No alerts recorded</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartData} barSize={22} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <XAxis
                  dataKey="name"
                  tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'Space Mono' }}
                  axisLine={false} tickLine={false}
                />
                <YAxis
                  tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'Space Mono' }}
                  axisLine={false} tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: 'rgba(0,229,204,0.05)' }}
                  contentStyle={{
                    background: 'var(--bg-700)',
                    border: '1px solid var(--border)',
                    borderRadius: 8,
                    fontSize: 12,
                    fontFamily: 'Space Mono',
                  }}
                  labelStyle={{ color: 'var(--text-1)' }}
                  itemStyle={{ color: 'var(--teal)' }}
                />
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} opacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent alerts feed */}
        <div className="card">
          <div className="card-header" style={{ justifyContent: 'space-between' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Bell size={13} color="var(--teal)" />
              Recent Alerts
            </span>
            <Link to="/alerts" style={{ fontSize: 10, color: 'var(--teal)', fontFamily: 'var(--font-mono)' }}>
              VIEW ALL →
            </Link>
          </div>
          {recentAlerts.length === 0 ? (
            <div className="empty-state" style={{ padding: '36px 0' }}>
              <AlertTriangle size={28} />
              <p>No alerts yet</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 220, overflowY: 'auto' }}>
              {recentAlerts.map(a => {
                const sev = SEV_ACCENT[a.severity] || { color: 'var(--cyan)', cls: 'info' }
                return (
                  <div key={a.alert_id} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 12px',
                    background: 'var(--bg-700)',
                    borderRadius: 'var(--radius)',
                    borderLeft: `2px solid ${sev.color}`,
                    opacity: a.acknowledged ? 0.4 : 1,
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {a.type.replace(/_/g, ' ')}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', marginTop: 1 }}>
                        CAM {a.camera_id} · {new Date(a.timestamp * 1000).toLocaleTimeString()}
                      </div>
                    </div>
                    <span className={`badge badge-${a.severity === 'CRITICAL' ? 'red' : a.severity === 'HIGH' ? 'orange' : a.severity === 'MEDIUM' ? 'yellow' : 'cyan'}`}>
                      {a.severity}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Camera status grid ── */}
      <div className="card">
        <div className="card-header" style={{ justifyContent: 'space-between' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Camera size={13} color="var(--teal)" />
            Camera Status
          </span>
          <Link to="/cameras" style={{ fontSize: 10, color: 'var(--teal)', fontFamily: 'var(--font-mono)' }}>
            MANAGE →
          </Link>
        </div>
        {cameras.length === 0 ? (
          <div className="empty-state" style={{ padding: '36px 0' }}>
            <Camera size={28} />
            <p>No cameras registered</p>
            <span>Go to Cameras to add your first source</span>
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 10,
          }}>
            {cameras.map(cam => {
              const isStreaming = health?.streaming_cams?.includes(cam.id)
              return (
                <div key={cam.id} style={{
                  padding: '12px 14px',
                  background: 'var(--bg-700)',
                  borderRadius: 'var(--radius)',
                  border: `1px solid ${isStreaming ? 'rgba(0,230,118,0.25)' : cam.is_active ? 'var(--border)' : 'var(--border-dim)'}`,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                }}>
                  <div style={{
                    width: 36, height: 36,
                    borderRadius: 'var(--radius)',
                    background: isStreaming ? 'rgba(0,230,118,0.1)' : 'var(--bg-600)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}>
                    {isStreaming
                      ? <div className="live-dot" />
                      : <Camera size={16} color="var(--text-3)" />
                    }
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {cam.name}
                    </div>
                    <div style={{ fontSize: 10, color: isStreaming ? 'var(--green)' : cam.is_active ? 'var(--text-3)' : 'var(--red)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                      {isStreaming ? '● STREAMING' : cam.is_active ? '◌ STARTING' : '○ INACTIVE'}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}