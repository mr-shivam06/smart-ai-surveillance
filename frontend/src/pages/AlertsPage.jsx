import { useState, useEffect, useCallback } from 'react'
import { alertAPI } from '../services/api'
import { Bell, CheckCheck, Filter, RefreshCw } from 'lucide-react'

const SEV_COLOR = {
  CRITICAL: 'badge-red',
  HIGH:     'badge-orange',
  MEDIUM:   'badge-yellow',
  INFO:     'badge-cyan',
}

const TYPES = [
  '', 'ACCIDENT_DETECTED', 'AMBULANCE_DETECTED',
  'CROWD_DETECTED', 'HEAVY_TRAFFIC', 'CONGESTION',
  'LOITERING', 'ZONE_ENTER', 'ZONE_EXIT',
]

export default function AlertsPage() {
  const [alerts,   setAlerts]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [filter,   setFilter]   = useState({ type:'', camera_id:-1 })
  const [count,    setCount]    = useState(0)

  const load = useCallback(() => {
    setLoading(true)
    alertAPI.list({
      limit: 100,
      alert_type: filter.type || undefined,
      camera_id: filter.camera_id >= 0 ? filter.camera_id : undefined,
    })
      .then(r => setAlerts(r.data))
      .finally(() => setLoading(false))
    alertAPI.count().then(r => setCount(r.data.unacknowledged)).catch(()=>{})
  }, [filter])

  useEffect(() => { load() }, [load])

  const ack = async id => {
    await alertAPI.acknowledge(id)
    load()
  }

  const ackAll = async () => {
    const unacked = alerts.filter(a => !a.acknowledged)
    await Promise.all(unacked.map(a => alertAPI.acknowledge(a.alert_id)))
    load()
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Alerts</h1>
          <p>{count} unacknowledged</p>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          {count > 0 && (
            <button className="btn btn-ghost" onClick={ackAll}>
              <CheckCheck size={15}/> Ack All
            </button>
          )}
          <button className="btn btn-ghost" onClick={load}>
            <RefreshCw size={15}/> Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom:20, display:'flex', gap:12, alignItems:'center', flexWrap:'wrap' }}>
        <Filter size={15} color="var(--text-3)"/>
        <select
          value={filter.type}
          onChange={e => setFilter(f => ({...f, type: e.target.value}))}
          style={{ minWidth:180 }}
        >
          {TYPES.map(t => (
            <option key={t} value={t}>{t || 'All Alert Types'}</option>
          ))}
        </select>
        <select
          value={filter.camera_id}
          onChange={e => setFilter(f => ({...f, camera_id: Number(e.target.value)}))}
          style={{ minWidth:140 }}
        >
          <option value={-1}>All Cameras</option>
          {[1,2,3,4].map(i => (
            <option key={i} value={i}>Camera {i}</option>
          ))}
        </select>
        <button
          className="btn btn-ghost"
          onClick={() => setFilter({ type:'', camera_id:-1 })}
          style={{ fontSize:12 }}
        >
          Clear filters
        </button>
      </div>

      {/* Alert list */}
      {loading ? (
        <div style={{ display:'flex', justifyContent:'center', padding:48 }}>
          <div className="spinner"/>
        </div>
      ) : alerts.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Bell size={32}/>
            <p style={{ marginTop:8 }}>No alerts</p>
            <p style={{ fontSize:12, marginTop:4 }}>Alerts appear here when the AI detects events</p>
          </div>
        </div>
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
          {alerts.map(a => (
            <div
              key={a.alert_id}
              className="card"
              style={{
                display:'flex', alignItems:'center', gap:16,
                padding:'14px 18px',
                borderLeft:`3px solid ${
                  a.severity === 'CRITICAL' ? 'var(--red)'    :
                  a.severity === 'HIGH'     ? 'var(--orange)' :
                  a.severity === 'MEDIUM'   ? 'var(--yellow)' :
                  'var(--cyan)'
                }`,
                opacity: a.acknowledged ? 0.55 : 1,
              }}
            >
              {/* ID */}
              <span style={{ fontSize:11, color:'var(--text-3)', minWidth:36 }}>
                #{a.alert_id}
              </span>

              {/* Severity badge */}
              <span className={`badge ${SEV_COLOR[a.severity] || 'badge-teal'}`}>
                {a.severity}
              </span>

              {/* Type + message */}
              <div style={{ flex:1 }}>
                <div style={{ fontWeight:600, fontSize:13, color:'var(--text-1)' }}>
                  {a.type.replace(/_/g,' ')}
                </div>
                <div style={{ fontSize:12, color:'var(--text-3)', marginTop:2 }}>
                  {a.message}
                </div>
              </div>

              {/* Camera */}
              <span style={{
                fontSize:12, color:'var(--text-3)',
                background:'var(--bg-700)',
                padding:'3px 8px', borderRadius:'var(--radius)',
              }}>
                Cam {a.camera_id}
              </span>

              {/* Time */}
              <span style={{ fontSize:11, color:'var(--text-3)', minWidth:70, textAlign:'right' }}>
                {new Date(a.timestamp * 1000).toLocaleTimeString()}
              </span>

              {/* Ack button */}
              {!a.acknowledged ? (
                <button
                  className="btn btn-ghost"
                  onClick={() => ack(a.alert_id)}
                  style={{ fontSize:11, padding:'5px 10px' }}
                >
                  <CheckCheck size={13}/> Ack
                </button>
              ) : (
                <span style={{ fontSize:11, color:'var(--green)', minWidth:50 }}>✓ Done</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}