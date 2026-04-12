// src/pages/TrackingPage.jsx
import { useState, useEffect } from 'react'
import { trackingAPI } from '../services/api'
import { Activity, RefreshCw, RotateCcw, Users } from 'lucide-react'

export default function TrackingPage() {
  const [status,  setStatus]  = useState(null)
  const [matches, setMatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [resetting, setResetting] = useState(false)

  const load = async () => {
    try {
      const [s, m] = await Promise.all([
        trackingAPI.status(),
        trackingAPI.crossCamera(),
      ])
      setStatus(s.data)
      setMatches(m.data)
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(() => { load(); const id = setInterval(load, 5000); return () => clearInterval(id) }, [])

  const reset = async () => {
    if (!confirm('Reset cross-camera gallery? All current IDs will be cleared.')) return
    setResetting(true)
    try { await trackingAPI.reset(); load() }
    finally { setResetting(false) }
  }

  if (loading) return <div style={{display:'flex',justifyContent:'center',padding:48}}><div className="spinner"/></div>

  return (
    <div>
      <div className="page-header">
        <div><h1>Tracking</h1><p>Cross-camera re-identification status</p></div>
        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-ghost" onClick={load}><RefreshCw size={14}/> Refresh</button>
          <button className="btn btn-danger" onClick={reset} disabled={resetting}>
            <RotateCcw size={14}/> {resetting ? 'Resetting...' : 'Reset Gallery'}
          </button>
        </div>
      </div>

      {/* Status cards */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16, marginBottom:24 }}>
        {[
          { label:'ReID Backend',      value: status?.reid_backend ?? '—',          color:'var(--purple)' },
          { label:'Total Identities',  value: status?.total_identities ?? 0,         color:'var(--teal)'   },
          { label:'Cross-Cam Matches', value: status?.cross_cam_matches ?? 0,        color:'var(--cyan)'   },
          { label:'Status',            value: status?.is_running ? 'Running' : 'Stopped', color:'var(--green)' },
        ].map(({ label, value, color }) => (
          <div key={label} className="stat-card">
            <div className="label">{label}</div>
            <div className="value" style={{ color, fontSize:20 }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Cross-camera matches */}
      <div className="card">
        <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:16 }}>
          Cross-Camera Identities
        </h3>
        {matches.length === 0 ? (
          <div className="empty-state">
            <Users size={32}/>
            <p style={{ marginTop:8 }}>No cross-camera matches yet</p>
            <p style={{ fontSize:12, marginTop:4 }}>
              Walk between cameras — the same person will get a shared Global ID
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Global ID</th><th>Class</th><th>Cameras</th></tr>
              </thead>
              <tbody>
                {matches.map(m => (
                  <tr key={m.global_id}>
                    <td><code style={{ color:'var(--teal)', fontFamily:'monospace' }}>{m.global_id}</code></td>
                    <td><span className="badge badge-cyan">{m.class_name}</span></td>
                    <td style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
                      {m.cameras.map(c => (
                        <span key={c} className="badge badge-teal">Cam {c}</span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* How it works */}
      <div className="card" style={{ marginTop:16 }}>
        <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:12 }}>
          How Cross-Camera ReID Works
        </h3>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:16 }}>
          {[
            { title:'1. Detect & Track', desc:'YOLO detects objects. DeepSort assigns a local ID per camera (C1-ID3, C2-ID7).' },
            { title:'2. Extract Embedding', desc:'Each tracked object is cropped and processed through OSNet (or HSV histogram) to get an appearance vector.' },
            { title:'3. Match & Assign', desc:'Cosine similarity between embeddings. Match > threshold → same Global ID (G-001) shown on both cameras.' },
          ].map(({ title, desc }) => (
            <div key={title} style={{
              padding:'14px 16px',
              background:'var(--bg-700)',
              borderRadius:'var(--radius)',
              borderTop:`2px solid var(--teal)`,
            }}>
              <div style={{ fontWeight:600, fontSize:13, color:'var(--teal)', marginBottom:6 }}>{title}</div>
              <div style={{ fontSize:12, color:'var(--text-3)', lineHeight:1.7 }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}