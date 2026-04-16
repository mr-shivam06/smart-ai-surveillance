import { useState, useEffect, useCallback } from 'react'
import { alertAPI, cameraAPI } from '../services/api'
import { Bell, CheckCheck, Filter, RefreshCw, Zap, X } from 'lucide-react'

const SEV = {
  CRITICAL: { cls: 'badge-red',    accent: 'var(--red)',    bg: 'rgba(255,61,90,0.05)'  },
  HIGH:     { cls: 'badge-orange', accent: 'var(--orange)', bg: 'rgba(255,140,66,0.05)' },
  MEDIUM:   { cls: 'badge-yellow', accent: 'var(--yellow)', bg: 'rgba(255,215,64,0.04)' },
  INFO:     { cls: 'badge-cyan',   accent: 'var(--cyan)',   bg: 'rgba(41,217,245,0.04)' },
}

const TYPES = [
  '', 'ACCIDENT_DETECTED', 'AMBULANCE_DETECTED',
  'CROWD_DETECTED', 'HEAVY_TRAFFIC', 'CONGESTION',
  'LOITERING', 'ZONE_ENTER', 'ZONE_EXIT',
]

export default function AlertsPage() {
  const [alerts,   setAlerts]   = useState([])
  const [cameras,  setCameras]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [count,    setCount]    = useState(0)
  const [filter,   setFilter]   = useState({ type: '', camera_id: -1 })
  const [acking,   setAcking]   = useState(new Set())

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [res, c, cams] = await Promise.all([
        alertAPI.list({
          limit: 150,
          alert_type: filter.type || undefined,
          camera_id: filter.camera_id >= 0 ? filter.camera_id : undefined,
        }),
        alertAPI.count(),
        cameraAPI.list(),
      ])
      setAlerts(res.data)
      setCount(c.data.unacknowledged)
      setCameras(cams.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }, [filter])

  useEffect(() => { load() }, [filter])

  useEffect(() => {
    const id = setInterval(() => {
      alertAPI.count().then(r => setCount(r.data.unacknowledged)).catch(() => {})
    }, 8000)
    return () => clearInterval(id)
  }, [])

  const ack = async id => {
    setAcking(s => new Set(s).add(id))
    try {
      await alertAPI.acknowledge(id)
      setAlerts(prev => prev.map(a => a.alert_id === id ? { ...a, acknowledged: true } : a))
      setCount(c => Math.max(0, c - 1))
    } finally {
      setAcking(s => { const n = new Set(s); n.delete(id); return n })
    }
  }

  const ackAll = async () => {
    const unacked = alerts.filter(a => !a.acknowledged)
    await Promise.all(unacked.map(a => ack(a.alert_id)))
  }

  const clearFilters = () => setFilter({ type: '', camera_id: -1 })
  const hasFilters = filter.type || filter.camera_id >= 0

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Alerts</div>
          <div className="page-sub" style={{ color: count > 0 ? 'var(--red)' : 'var(--text-3)' }}>
            {count > 0 ? `${count} UNACKNOWLEDGED` : 'ALL CLEAR'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {count > 0 && (
            <button className="btn btn-ghost btn-sm" onClick={ackAll}>
              <CheckCheck size={13} /> Ack All ({count})
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={load}>
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: 20, padding: '14px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-3)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
            <Filter size={13} /> FILTER
          </div>
          <select
            value={filter.type}
            onChange={e => setFilter(f => ({ ...f, type: e.target.value }))}
            style={{ width: 'auto', minWidth: 180 }}
          >
            {TYPES.map(t => (
              <option key={t} value={t}>{t || 'All Alert Types'}</option>
            ))}
          </select>
          <select
            value={filter.camera_id}
            onChange={e => setFilter(f => ({ ...f, camera_id: Number(e.target.value) }))}
            style={{ width: 'auto', minWidth: 140 }}
          >
            <option value={-1}>All Cameras</option>
            {cameras.map(cam => (
              <option key={cam.id} value={cam.id}>{cam.name}</option>
            ))}
          </select>
          {hasFilters && (
            <button className="btn btn-ghost btn-sm" onClick={clearFilters}>
              <X size={12} /> Clear
            </button>
          )}
          <div style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
            {alerts.length} RESULTS
          </div>
        </div>
      </div>

      {/* Alert list */}
      {loading ? (
        <div className="loading-screen"><div className="spinner" />LOADING ALERTS...</div>
      ) : alerts.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Bell size={32} />
            <p>No alerts found</p>
            {hasFilters && <span>Try clearing the filters</span>}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {alerts.map(a => {
            const sev = SEV[a.severity] || SEV.INFO
            return (
              <div
                key={a.alert_id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 14,
                  padding: '13px 18px',
                  background: a.acknowledged ? 'var(--bg-800)' : sev.bg,
                  border: `1px solid ${a.acknowledged ? 'var(--border-dim)' : 'var(--border)'}`,
                  borderLeft: `3px solid ${a.acknowledged ? 'var(--border)' : sev.accent}`,
                  borderRadius: 'var(--radius-lg)',
                  opacity: a.acknowledged ? 0.45 : 1,
                  transition: 'opacity 0.2s',
                }}
              >
                {/* ID */}
                <span style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', minWidth: 34 }}>
                  #{a.alert_id}
                </span>

                {/* Severity badge */}
                <span className={`badge ${sev.cls}`}>{a.severity}</span>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-1)' }}>
                    {a.type.replace(/_/g, ' ')}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>
                    {a.message}
                  </div>
                </div>

                {/* Camera */}
                <div style={{
                  fontSize: 10, color: 'var(--text-3)',
                  background: 'var(--bg-700)',
                  border: '1px solid var(--border)',
                  padding: '3px 9px', borderRadius: 20,
                  fontFamily: 'var(--font-mono)',
                  whiteSpace: 'nowrap',
                }}>
                  CAM {a.camera_id}
                </div>

                {/* Time */}
                <span style={{ fontSize: 10, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', minWidth: 68, textAlign: 'right' }}>
                  {new Date(a.timestamp * 1000).toLocaleTimeString()}
                </span>

                {/* Ack button */}
                {!a.acknowledged ? (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => ack(a.alert_id)}
                    disabled={acking.has(a.alert_id)}
                    style={{ flexShrink: 0 }}
                  >
                    {acking.has(a.alert_id)
                      ? <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
                      : <><CheckCheck size={12} /> Ack</>
                    }
                  </button>
                ) : (
                  <span style={{ fontSize: 10, color: 'var(--green)', fontFamily: 'var(--font-mono)', minWidth: 44 }}>
                    ✓ DONE
                  </span>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}