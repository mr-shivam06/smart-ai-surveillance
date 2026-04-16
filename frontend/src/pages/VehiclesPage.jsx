import { useState, useEffect } from 'react'
import { vehicleAPI } from '../services/api'
import { Car, Search, RefreshCw, Clock, Camera } from 'lucide-react'

const COLORS = ['','red','blue','white','black','silver','green','yellow','orange','gray']
const SHAPES = ['','sedan','suv/hatchback','van/truck','compact','motorcycle','bicycle','bus','truck']

const COLOR_SWATCH = {
  red:    '#ef4444', blue:   '#3b82f6', white:  '#e2e8f0',
  black:  '#1e293b', silver: '#94a3b8', green:  '#22c55e',
  yellow: '#eab308', orange: '#f97316', gray:   '#6b7280',
}

function timeSince(ts) {
  const s = Math.floor((Date.now() / 1000) - ts)
  if (s < 60)  return `${s}s ago`
  if (s < 3600) return `${Math.floor(s/60)}m ago`
  return `${Math.floor(s/3600)}h ago`
}

export default function VehiclesPage() {
  const [vehicles, setVehicles] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [color,    setColor]    = useState('')
  const [shape,    setShape]    = useState('')

  const load = () => {
    setLoading(true)
    const req = (color || shape)
      ? vehicleAPI.search(color, shape)
      : vehicleAPI.list(200)
    req.then(r => setVehicles(r.data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Vehicles</div>
          <div className="page-sub">{vehicles.length} RECORDS · INTELLIGENCE DATABASE</div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}>
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* Search */}
      <div className="card" style={{ marginBottom: 20, padding: '14px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <label style={{ fontSize: 10, color: 'var(--text-3)', display: 'block', marginBottom: 6, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
              COLOR
            </label>
            <select value={color} onChange={e => setColor(e.target.value)} style={{ width: 150 }}>
              {COLORS.map(c => <option key={c} value={c}>{c || 'Any Color'}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize: 10, color: 'var(--text-3)', display: 'block', marginBottom: 6, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
              SHAPE TYPE
            </label>
            <select value={shape} onChange={e => setShape(e.target.value)} style={{ width: 170 }}>
              {SHAPES.map(s => <option key={s} value={s}>{s || 'Any Shape'}</option>)}
            </select>
          </div>
          <button className="btn btn-primary btn-sm" onClick={load} style={{ marginBottom: 1 }}>
            <Search size={13} /> Search
          </button>
          {(color || shape) && (
            <button className="btn btn-ghost btn-sm" onClick={() => { setColor(''); setShape(''); }}
              style={{ marginBottom: 1 }}>
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <div className="loading-screen"><div className="spinner" />QUERYING DATABASE...</div>
      ) : vehicles.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Car size={32} />
            <p>No vehicles found</p>
            <span>Vehicles are detected and logged automatically</span>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Global ID</th>
                  <th>Class</th>
                  <th>Color</th>
                  <th>Shape</th>
                  <th>Cameras</th>
                  <th>Frames</th>
                  <th>Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {vehicles.map(v => (
                  <tr key={v.global_id}>
                    <td>
                      <span style={{
                        fontFamily: 'var(--font-mono)', fontSize: 12,
                        color: 'var(--orange)',
                        background: 'rgba(255,140,66,0.08)',
                        padding: '3px 8px', borderRadius: 4,
                      }}>
                        {v.global_id}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-orange">{v.class_name}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {v.color && (
                          <div style={{
                            width: 12, height: 12,
                            borderRadius: 3,
                            background: COLOR_SWATCH[v.color] || '#666',
                            border: '1px solid rgba(255,255,255,0.15)',
                            flexShrink: 0,
                          }} />
                        )}
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-2)' }}>
                          {v.color || '—'}
                        </span>
                      </div>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-2)' }}>
                      {v.shape_type || '—'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {v.cameras?.toString().split(',').map(c => (
                          <span key={c} style={{
                            fontSize: 10, fontFamily: 'var(--font-mono)',
                            color: 'var(--cyan)',
                            background: 'rgba(41,217,245,0.08)',
                            border: '1px solid rgba(41,217,245,0.2)',
                            padding: '2px 6px', borderRadius: 10,
                          }}>
                            {c}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-3)' }}>
                      {v.frame_count}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                        <Clock size={11} />
                        {timeSince(v.last_seen)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}