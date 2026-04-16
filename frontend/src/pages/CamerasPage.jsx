import { useState, useEffect } from 'react'
import { cameraAPI } from '../services/api'
import CameraFeed from '../components/CameraFeed'
import { Camera, Plus, Trash2, ToggleLeft, ToggleRight, Wifi, X, Maximize2 } from 'lucide-react'

export default function CamerasPage() {
  const [cameras,  setCameras]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [adding,   setAdding]   = useState(false)
  const [form,     setForm]     = useState({ name: '', source: '' })
  const [error,    setError]    = useState('')
  const [showForm, setShowForm] = useState(false)
  const [expanded, setExpanded] = useState(null)

  const load = () =>
    cameraAPI.list()
      .then(r => setCameras(r.data))
      .catch(console.error)
      .finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const addCamera = async e => {
    e.preventDefault()
    setError(''); setAdding(true)
    try {
      await cameraAPI.add(form)
      setForm({ name: '', source: '' })
      setShowForm(false)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add camera')
    } finally { setAdding(false) }
  }

  const remove = async id => {
    if (!confirm('Remove this camera?')) return
    await cameraAPI.delete(id)
    if (expanded === id) setExpanded(null)
    load()
  }

  const toggle = async id => { await cameraAPI.toggle(id); load() }

  const activeCams = cameras.filter(c => c.is_active)

  if (loading) return <div className="loading-screen"><div className="spinner" />LOADING CAMERAS...</div>

  return (
    <div className="fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">Live Cameras</div>
          <div className="page-sub">{activeCams.length} ACTIVE · {cameras.length} REGISTERED</div>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setShowForm(s => !s)}>
          <Plus size={14} /> Add Camera
        </button>
      </div>

      {/* Add camera form */}
      {showForm && (
        <div className="card fade-in" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-3)', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
              ADD CAMERA SOURCE
            </div>
            <button className="btn-icon" onClick={() => setShowForm(false)}>
              <X size={14} />
            </button>
          </div>
          <form onSubmit={addCamera} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12 }}>
              <div>
                <label style={{ fontSize: 10, color: 'var(--text-3)', display: 'block', marginBottom: 6, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
                  NAME
                </label>
                <input
                  placeholder="Front Door"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  required
                />
              </div>
              <div>
                <label style={{ fontSize: 10, color: 'var(--text-3)', display: 'block', marginBottom: 6, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
                  SOURCE
                </label>
                <input
                  placeholder="0  or  http://192.168.x.x:4747/video"
                  value={form.source}
                  onChange={e => setForm(f => ({ ...f, source: e.target.value }))}
                  required
                />
              </div>
            </div>
            {error && (
              <div style={{
                padding: '8px 12px',
                background: 'var(--red-dim)',
                border: '1px solid rgba(255,61,90,0.25)',
                borderRadius: 'var(--radius)',
                color: 'var(--red)', fontSize: 12,
                fontFamily: 'var(--font-mono)',
              }}>
                ⚠ {error}
              </div>
            )}
            <div style={{
              padding: '10px 14px',
              background: 'var(--bg-700)',
              borderRadius: 'var(--radius)',
              fontSize: 11, color: 'var(--text-3)',
              fontFamily: 'var(--font-mono)',
              lineHeight: 2,
            }}>
              <code style={{ color: 'var(--teal)' }}>0</code> = built-in webcam &nbsp;·&nbsp;
              <code style={{ color: 'var(--teal)' }}>1</code> = USB cam &nbsp;·&nbsp;
              <code style={{ color: 'var(--teal)' }}>http://IP:4747/video</code> = DroidCam
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" className="btn btn-primary btn-sm" disabled={adding}>
                {adding ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Adding...</> : 'Add Camera'}
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Fullscreen modal */}
      {expanded !== null && (() => {
        const cam = cameras.find(c => c.id === expanded)
        if (!cam) return null
        return (
          <div className="fullscreen-modal" onClick={() => setExpanded(null)}>
            <div
              style={{ width: '100%', maxWidth: 1000, position: 'relative' }}
              onClick={e => e.stopPropagation()}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-1)' }}>
                  {cam.name}
                  <span style={{ marginLeft: 10, fontSize: 10, color: 'var(--teal)', fontFamily: 'var(--font-mono)' }}>EXPANDED VIEW</span>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => setExpanded(null)}>
                  <X size={14} /> Close
                </button>
              </div>
              <CameraFeed cameraId={cam.id} name={cam.name} width={960} height={720} />
            </div>
          </div>
        )
      })()}

      {/* No cameras */}
      {cameras.length === 0 && (
        <div className="card">
          <div className="empty-state">
            <Camera size={32} />
            <p>No cameras registered</p>
            <span>Add a camera above to start monitoring</span>
          </div>
        </div>
      )}

      {/* Live feed grid */}
      {activeCams.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <div className="section-label">Live Feeds</div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: activeCams.length === 1 ? '1fr' : 'repeat(auto-fill, minmax(440px, 1fr))',
            gap: 14,
          }}>
            {activeCams.map(cam => (
              <div key={cam.id} className="feed-wrapper live">
                <CameraFeed
                  cameraId={cam.id}
                  name={cam.name}
                  width={480}
                  height={360}
                  onClick={() => setExpanded(cam.id)}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Management table */}
      {cameras.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px 0' }}>
            <div className="card-header">
              <Camera size={13} color="var(--teal)" />
              Camera Management
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>Name</th><th>Source</th><th>Status</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {cameras.map(cam => (
                  <tr key={cam.id}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-3)' }}>
                      #{cam.id}
                    </td>
                    <td style={{ fontWeight: 600, color: 'var(--text-1)' }}>{cam.name}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Wifi size={12} color="var(--text-3)" />
                        <code style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-2)' }}>
                          {cam.source}
                        </code>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${cam.is_active ? 'badge-green' : 'badge-red'}`}>
                        {cam.is_active ? '● ACTIVE' : '○ INACTIVE'}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => toggle(cam.id)}>
                          {cam.is_active ? <><ToggleRight size={13} /> Disable</> : <><ToggleLeft size={13} /> Enable</>}
                        </button>
                        {cam.is_active && (
                          <button className="btn btn-ghost btn-sm" onClick={() => setExpanded(cam.id)}>
                            <Maximize2 size={13} />
                          </button>
                        )}
                        <button className="btn btn-danger btn-sm" onClick={() => remove(cam.id)}>
                          <Trash2 size={13} />
                        </button>
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