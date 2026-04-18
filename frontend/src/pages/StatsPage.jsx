import { useState, useEffect, useRef, useCallback } from 'react'
import { healthAPI, alertAPI, trackingAPI, cameraAPI } from '../services/api'
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
  Cell, PieChart, Pie, Legend
} from 'recharts'
import {
  Activity, AlertTriangle, Shield, Flame,
  Users, Car, Radio, TrendingUp, RefreshCw, Zap
} from 'lucide-react'

// ── custom hook: stable interval ──────────────────────────────
function useInterval(fn, ms) {
  const cb = useRef(fn)
  useEffect(() => { cb.current = fn }, [fn])
  useEffect(() => {
    const id = setInterval(() => cb.current(), ms)
    return () => clearInterval(id)
  }, [ms])
}

const SEV_COLOR = {
  CRITICAL: 'var(--red)',
  HIGH:     'var(--orange)',
  MEDIUM:   'var(--yellow)',
  INFO:     'var(--cyan)',
}

const PIE_COLORS = [
  'var(--red)', 'var(--orange)', 'var(--yellow)',
  'var(--teal)', 'var(--cyan)', 'var(--purple)',
]

function StatCard({ label, value, sub, icon: Icon, color, pulse }) {
  return (
    <div style={{
      background: 'var(--bg-800)',
      border: `1px solid ${pulse ? color : 'var(--border)'}`,
      borderRadius: 'var(--radius-lg)',
      padding: '16px 20px',
      position: 'relative',
      overflow: 'hidden',
      boxShadow: pulse ? `0 0 16px ${color}33` : 'none',
      transition: 'box-shadow 0.3s, border-color 0.3s',
    }}>
      {pulse && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, height: 2,
          background: color, opacity: 0.8,
        }}/>
      )}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 10 }}>
        <span style={{ fontSize:11, color:'var(--text-3)', textTransform:'uppercase', letterSpacing:'0.08em' }}>
          {label}
        </span>
        <Icon size={16} color={color}/>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize:11, color:'var(--text-3)', marginTop:5 }}>{sub}</div>}
    </div>
  )
}

const TOOLTIP_STYLE = {
  contentStyle: {
    background: 'var(--bg-700)', border: '1px solid var(--border)',
    borderRadius: 8, fontSize: 12,
  },
  labelStyle: { color: 'var(--text-1)' },
  itemStyle:  { color: 'var(--teal)' },
}

export default function StatsPage() {
  const [health,    setHealth]    = useState(null)
  const [alerts,    setAlerts]    = useState([])
  const [tracking,  setTracking]  = useState(null)
  const [cameras,   setCameras]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [lastUpdate,setLastUpdate] = useState(null)

  // Time-series for area charts (last 30 data points)
  const [idHistory,   setIdHistory]   = useState([])
  const [crossHistory,setCrossHistory] = useState([])
  const [alertHistory,setAlertHistory] = useState([])

  const fetchAll = useCallback(async (quiet = false) => {
    try {
      const [h, a, t, c] = await Promise.all([
        healthAPI.check(),
        alertAPI.list({ limit: 100 }),
        trackingAPI.status(),
        cameraAPI.list(),
      ])
      setHealth(h.data)
      setAlerts(a.data)
      setTracking(t.data)
      setCameras(c.data)

      const tick = new Date().toLocaleTimeString('en', { hour12: false, hour:'2-digit', minute:'2-digit', second:'2-digit' })

      setIdHistory(prev => [...prev.slice(-29), {
        t: tick,
        ids:   h.data.global_ids      ?? 0,
        cross: h.data.cross_cam       ?? 0,
      }])

      setAlertHistory(prev => [...prev.slice(-29), {
        t:       tick,
        unacked: h.data.unacked_alerts ?? 0,
        total:   a.data.length,
      }])

      setLastUpdate(new Date().toLocaleTimeString())
    } catch(e) {
      console.error('[StatsPage]', e)
    } finally {
      if (!quiet) setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])
  useInterval(() => fetchAll(true), 3000)

  // ── Derived stats ─────────────────────────────────────────
  const unacked   = alerts.filter(a => !a.acknowledged).length
  const hasFire   = alerts.some(a =>
    a.type === 'FIRE_DETECTED' && !a.acknowledged &&
    Date.now()/1000 - a.timestamp < 30
  )
  const hasSmoke  = alerts.some(a =>
    a.type === 'SMOKE_DETECTED' && !a.acknowledged &&
    Date.now()/1000 - a.timestamp < 30
  )

  const typeCounts = alerts.reduce((acc, a) => {
    const k = a.type.replace(/_?DETECTED/,'').replace(/_/g,' ').trim()
    acc[k] = (acc[k] || 0) + 1
    return acc
  }, {})
  const pieData   = Object.entries(typeCounts).map(([name, value]) => ({ name, value }))
  const barData   = Object.entries(typeCounts)
    .sort((a,b) => b[1]-a[1])
    .map(([name, count]) => ({ name, count }))

  const activeCams    = cameras.filter(c => c.is_active).length
  const streamingCams = health?.streaming_cams?.length ?? 0

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:240 }}>
      <div className="spinner"/>
    </div>
  )

  return (
    <div>
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1>Analytics</h1>
          <p>Live system stats — updates every 3s{lastUpdate ? ` · last ${lastUpdate}` : ''}</p>
        </div>
        <button className="btn btn-ghost" onClick={() => fetchAll()}>
          <RefreshCw size={14}/> Refresh
        </button>
      </div>

      {/* ── Fire/Smoke banner ── */}
      {(hasFire || hasSmoke) && (
        <div style={{
          marginBottom: 20,
          padding: '14px 20px',
          background: hasFire ? 'rgba(255,61,90,0.12)' : 'rgba(160,160,160,0.1)',
          border: `1px solid ${hasFire ? 'var(--red)' : '#888'}`,
          borderRadius: 'var(--radius-lg)',
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <Flame size={22} color={hasFire ? 'var(--red)' : '#aaa'}/>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: hasFire ? 'var(--red)' : '#ccc' }}>
              {hasFire ? '🔥 FIRE DETECTED — check camera feed immediately' : '💨 Smoke detected'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-3)', marginTop: 2 }}>
              Alert active in the last 30 seconds
            </div>
          </div>
          <span className={`badge ${hasFire ? 'badge-red' : 'badge-yellow'}`} style={{ marginLeft:'auto' }}>
            {hasFire ? 'CRITICAL' : 'HIGH'}
          </span>
        </div>
      )}

      {/* ── Stat cards ── */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16, marginBottom:24 }}>
        <StatCard
          label="Active Cameras"
          value={activeCams}
          sub={`${streamingCams} streaming to dashboard`}
          icon={Radio}
          color="var(--teal)"
        />
        <StatCard
          label="Global Identities"
          value={health?.global_ids ?? '—'}
          sub={`${health?.cross_cam ?? 0} cross-camera`}
          icon={Users}
          color="var(--cyan)"
        />
        <StatCard
          label="Unacked Alerts"
          value={unacked}
          sub={`${alerts.length} total in session`}
          icon={AlertTriangle}
          color={unacked > 0 ? 'var(--red)' : 'var(--green)'}
          pulse={unacked > 0}
        />
        <StatCard
          label="ReID Backend"
          value={tracking?.reid_backend ?? '—'}
          sub={`${tracking?.cross_cam_matches ?? 0} matches active`}
          icon={Shield}
          color="var(--purple)"
        />
      </div>

      {/* ── Charts row 1 ── */}
      <div style={{ display:'grid', gridTemplateColumns:'2fr 1fr', gap:20, marginBottom:20 }}>

        {/* Identity trend */}
        <div className="card">
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16 }}>
            <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)' }}>
              Identity Tracking — Live
            </h3>
            <span style={{ fontSize:11, color:'var(--text-3)' }}>Last 30 ticks · 3s interval</span>
          </div>
          {idHistory.length < 2 ? (
            <div style={{ color:'var(--text-3)', fontSize:12, padding:'20px 0' }}>
              Collecting data…
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={idHistory}>
                <defs>
                  <linearGradient id="gIds" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--teal)"  stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="var(--teal)"  stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="gCross" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--cyan)"  stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="var(--cyan)"  stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" tick={{ fill:'var(--text-3)', fontSize:10 }}
                       axisLine={false} tickLine={false} interval="preserveStartEnd"/>
                <YAxis tick={{ fill:'var(--text-3)', fontSize:10 }}
                       axisLine={false} tickLine={false} width={28}/>
                <Tooltip {...TOOLTIP_STYLE}/>
                <Area type="monotone" dataKey="ids"   name="Total IDs"
                      stroke="var(--teal)" fill="url(#gIds)"   strokeWidth={2}/>
                <Area type="monotone" dataKey="cross" name="Cross-Cam"
                      stroke="var(--cyan)" fill="url(#gCross)" strokeWidth={2}/>
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Alert type pie */}
        <div className="card">
          <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:16 }}>
            Alert Breakdown
          </h3>
          {pieData.length === 0 ? (
            <div style={{ color:'var(--text-3)', fontSize:12, padding:'40px 0', textAlign:'center' }}>
              No alerts yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name"
                     cx="50%" cy="50%" outerRadius={70} innerRadius={40}
                     paddingAngle={3}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]}/>
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background:'var(--bg-700)', border:'1px solid var(--border)', borderRadius:8, fontSize:11 }}/>
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── Charts row 2 ── */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:20 }}>

        {/* Alert count trend */}
        <div className="card">
          <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:16 }}>
            Alert Activity
          </h3>
          {alertHistory.length < 2 ? (
            <div style={{ color:'var(--text-3)', fontSize:12, padding:'20px 0' }}>Collecting…</div>
          ) : (
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={alertHistory}>
                <defs>
                  <linearGradient id="gUnacked" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--red)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--red)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" tick={{ fill:'var(--text-3)', fontSize:10 }}
                       axisLine={false} tickLine={false} interval="preserveStartEnd"/>
                <YAxis tick={{ fill:'var(--text-3)', fontSize:10 }}
                       axisLine={false} tickLine={false} width={24}/>
                <Tooltip {...TOOLTIP_STYLE}/>
                <Area type="monotone" dataKey="unacked" name="Unacked"
                      stroke="var(--red)" fill="url(#gUnacked)" strokeWidth={2}/>
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Alert bar chart by type */}
        <div className="card">
          <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:16 }}>
            Alert Types
          </h3>
          {barData.length === 0 ? (
            <div style={{ color:'var(--text-3)', fontSize:12, padding:'20px 0' }}>No alerts</div>
          ) : (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={barData} barSize={20}>
                <XAxis dataKey="name" tick={{ fill:'var(--text-3)', fontSize:10 }}
                       axisLine={false} tickLine={false}/>
                <YAxis tick={{ fill:'var(--text-3)', fontSize:10 }}
                       axisLine={false} tickLine={false} width={24}/>
                <Tooltip {...TOOLTIP_STYLE}/>
                <Bar dataKey="count" radius={[4,4,0,0]}>
                  {barData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]}/>
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── Recent critical alerts ── */}
      <div className="card">
        <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:14 }}>
          Recent Alerts
        </h3>
        {alerts.length === 0 ? (
          <div className="empty-state" style={{ padding:'24px 0' }}>
            <AlertTriangle size={28}/>
            <p style={{ marginTop:8 }}>No alerts in this session</p>
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
            {alerts.slice(0, 10).map(a => (
              <div key={a.alert_id} style={{
                display:'flex', alignItems:'center', gap:12,
                padding:'10px 14px',
                background:'var(--bg-700)',
                borderRadius:'var(--radius)',
                borderLeft:`3px solid ${SEV_COLOR[a.severity] || 'var(--border)'}`,
                opacity: a.acknowledged ? 0.5 : 1,
              }}>
                <span style={{ fontSize:11, color:'var(--text-3)', minWidth:32 }}>
                  #{a.alert_id}
                </span>
                <span className={`badge badge-${
                  a.severity==='CRITICAL'?'red':a.severity==='HIGH'?'orange':
                  a.severity==='MEDIUM'?'yellow':'cyan'
                }`}>
                  {a.severity}
                </span>
                <div style={{ flex:1 }}>
                  <div style={{ fontSize:12, fontWeight:600, color:'var(--text-1)' }}>
                    {a.type.replace(/_/g,' ')}
                  </div>
                  <div style={{ fontSize:11, color:'var(--text-3)' }}>
                    Cam {a.camera_id} · {a.message}
                  </div>
                </div>
                <span style={{ fontSize:11, color:'var(--text-3)' }}>
                  {new Date(a.timestamp*1000).toLocaleTimeString()}
                </span>
                {a.acknowledged && (
                  <span style={{ fontSize:11, color:'var(--green)' }}>✓</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}