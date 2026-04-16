import { useState, useEffect } from 'react'
import { trackingAPI } from '../services/api'
import { Activity, RefreshCw, RotateCcw, Users, Cpu, GitMerge, CheckCircle } from 'lucide-react'

export default function TrackingPage() {
  const [status,    setStatus]    = useState(null)
  const [matches,   setMatches]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [resetting, setResetting] = useState(false)

  const load = async () => {
    try {
      const [s, m] = await Promise.all([
        trackingAPI.status(),
        trackingAPI.crossCamera(),
      ])
      setStatus(s.data)
      setMatches(m.data)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [])

  const reset = async () => {
    if (!confirm('Reset cross-camera gallery? All current global IDs will be cleared.')) return
    setResetting(true)
    try { await trackingAPI.reset(); load() }
    finally { setResetting(false) }
  }

  if (loading) return <div className="loading-screen"><div className="spinner" />LOADING TRACKING DATA...</div>

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Tracking</div>
          <div className="page-sub">CROSS-CAMERA RE-IDENTIFICATION · LIVE</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={load}>
            <RefreshCw size={13} /> Refresh
          </button>
          <button className="btn btn-danger btn-sm" onClick={reset} disabled={resetting}>
            <RotateCcw size={13} /> {resetting ? 'Resetting...' : 'Reset Gallery'}
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        {[
          {
            label: 'ReID Backend',
            value: status?.reid_backend ?? '—',
            icon: Cpu,
            color: 'var(--purple)',
            sub: 'Embedding model',
          },
          {
            label: 'Total Identities',
            value: status?.total_identities ?? 0,
            icon: Users,
            color: 'var(--teal)',
            sub: 'In gallery',
          },
          {
            label: 'Cross-Cam Matches',
            value: status?.cross_cam_matches ?? 0,
            icon: GitMerge,
            color: 'var(--cyan)',
            sub: 'Same person, multiple cams',
          },
          {
            label: 'Status',
            value: status?.is_running ? 'RUNNING' : 'STOPPED',
            icon: CheckCircle,
            color: status?.is_running ? 'var(--green)' : 'var(--red)',
            sub: 'Pipeline state',
          },
        ].map(({ label, value, icon: Icon, color, sub }) => (
          <div key={label} className="stat-card">
            <div className="sc-label">{label}<Icon size={13} color={color} /></div>
            <div className="sc-value" style={{ color, fontSize: value?.toString().length > 6 ? 18 : 28 }}>{value}</div>
            <div className="sc-sub">{sub}</div>
          </div>
        ))}
      </div>

      {/* Cross-camera matches table */}
      <div className="card">
        <div className="card-header">
          <GitMerge size={13} color="var(--teal)" />
          Cross-Camera Identities
          {matches.length > 0 && (
            <span className="badge badge-teal" style={{ marginLeft: 'auto' }}>{matches.length}</span>
          )}
        </div>

        {matches.length === 0 ? (
          <div className="empty-state">
            <Users size={32} />
            <p>No cross-camera matches yet</p>
            <span>Walk between cameras — same person gets a shared Global ID</span>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Global ID</th>
                  <th>Class</th>
                  <th>Cameras</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {matches.map(m => (
                  <tr key={m.global_id}>
                    <td>
                      <span style={{
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--teal)',
                        fontSize: 12,
                        background: 'var(--teal-glow)',
                        padding: '3px 8px',
                        borderRadius: 4,
                      }}>
                        {m.global_id}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-purple">{m.class_name}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                        {m.cameras?.map(c => (
                          <span key={c} style={{
                            fontSize: 10,
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--cyan)',
                            background: 'rgba(41,217,245,0.08)',
                            border: '1px solid rgba(41,217,245,0.2)',
                            padding: '2px 7px',
                            borderRadius: 10,
                          }}>
                            CAM {c}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-green">MATCHED</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}