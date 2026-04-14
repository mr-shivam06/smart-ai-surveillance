import { useState, useEffect } from 'react'
import { cameraAPI } from '../services/api'
import CameraFeed from '../components/CameraFeed'
import { Camera, Plus, Trash2, ToggleLeft, ToggleRight,
         Wifi, Maximize2, X } from 'lucide-react'

export default function CamerasPage() {
  const [cameras,   setCameras]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [adding,    setAdding]    = useState(false)
  const [form,      setForm]      = useState({ name: '', source: '' })
  const [error,     setError]     = useState('')
  const [showForm,  setShowForm]  = useState(false)
  const [expanded,  setExpanded]  = useState(null)   // expanded camera id

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

  const toggle = async id => {
    await cameraAPI.toggle(id)
    load()
  }

  const activeCams = cameras.filter(c => c.is_active)

  if (loading) return (
    <div style={{ display:'flex', justifyContent:'center', padding:48 }}>
      <div className="spinner"/>
    </div>
  )

  return (
    <div>
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1>Live Cameras</h1>
          <p>{activeCams.length} active · {cameras.length} total</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(s => !s)}>
          <Plus size={15}/> Add Camera
        </button>
      </div>

      {/* ── Add form ── */}
      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize:13, fontWeight:600, marginBottom:14 }}>Add New Camera</h3>
          <form onSubmit={addCamera} style={{ display:'flex', flexDirection:'column', gap:12 }}>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 2fr', gap:12 }}>
              <div>
                <label style={{ fontSize:12, color:'var(--text-3)', display:'block', marginBottom:5 }}>
                  Name
                </label>
                <input
                  placeholder="e.g. Front Door"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  required style={{ width:'100%' }}
                />
              </div>
              <div>
                <label style={{ fontSize:12, color:'var(--text-3)', display:'block', marginBottom:5 }}>
                  Source
                </label>
                <input
                  placeholder="0  or  http://192.168.x.x:4747/video"
                  value={form.source}
                  onChange={e => setForm(f => ({ ...f, source: e.target.value }))}
                  required style={{ width:'100%' }}
                />
              </div>
            </div>
            {error && <div style={{ color:'var(--red)', fontSize:12 }}>{error}</div>}
            <div style={{ display:'flex', gap:8 }}>
              <button type="submit" className="btn btn-primary" disabled={adding}>
                {adding ? 'Adding...' : 'Add Camera'}
              </button>
              <button type="button" className="btn btn-ghost"
                      onClick={() => setShowForm(false)}>Cancel</button>
            </div>
          </form>

          <div style={{
            marginTop:14, padding:'10px 14px',
            background:'var(--bg-700)', borderRadius:'var(--radius)',
            fontSize:11, color:'var(--text-3)', lineHeight:1.9,
          }}>
            <strong style={{ color:'var(--text-2)' }}>Source:</strong>
            &nbsp;<code style={{ color:'var(--teal)' }}>0</code> = webcam &nbsp;·&nbsp;
            <code style={{ color:'var(--teal)' }}>1</code> = USB cam &nbsp;·&nbsp;
            <code style={{ color:'var(--teal)' }}>http://IP:4747/video</code> = DroidCam
          </div>
        </div>
      )}

      {/* ── Expanded single camera view ── */}
      {expanded !== null && (() => {
        const cam = cameras.find(c => c.id === expanded)
        if (!cam) return null
        return (
          <div style={{ marginBottom:20 }}>
            <div style={{ display:'flex', justifyContent:'space-between',
                          alignItems:'center', marginBottom:10 }}>
              <h2 style={{ fontSize:15, fontWeight:600 }}>{cam.name} — Full View</h2>
              <button className="btn btn-ghost" onClick={() => setExpanded(null)}>
                <X size={15}/> Close
              </button>
            </div>
            <CameraFeed
              cameraId={cam.id}
              name={cam.name}
              width={960}
              height={720}
            />
          </div>
        )
      })()}

      {/* ── Camera grid ── */}
      {cameras.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Camera size={32}/>
            <p style={{ marginTop:8 }}>No cameras added yet</p>
            <p style={{ fontSize:12, marginTop:4 }}>
              Click "Add Camera" to register your first source
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* Live feed grid */}
          {activeCams.length > 0 && (
            <div style={{ marginBottom:24 }}>
              <h2 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)',
                           marginBottom:12 }}>
                Live Feeds
              </h2>
              <div style={{
                display: 'grid',
                gridTemplateColumns: activeCams.length === 1
                  ? '1fr'
                  : 'repeat(auto-fill, minmax(440px, 1fr))',
                gap: 16,
              }}>
                {activeCams.map(cam => (
                  <CameraFeed
                    key={cam.id}
                    cameraId={cam.id}
                    name={cam.name}
                    width={480}
                    height={360}
                    onClick={() => setExpanded(cam.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Camera management table */}
          <div className="card">
            <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:14 }}>
              Camera Management
            </h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>ID</th><th>Name</th><th>Source</th>
                    <th>Status</th><th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {cameras.map(cam => (
                    <tr key={cam.id}>
                      <td style={{ color:'var(--text-3)' }}>#{cam.id}</td>
                      <td style={{ fontWeight:500, color:'var(--text-1)' }}>{cam.name}</td>
                      <td>
                        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                          <Wifi size={12} color="var(--text-3)"/>
                          <code style={{ fontSize:11 }}>{cam.source}</code>
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${cam.is_active ? 'badge-green' : 'badge-red'}`}>
                          {cam.is_active ? '● Active' : '○ Inactive'}
                        </span>
                      </td>
                      <td>
                        <div style={{ display:'flex', gap:6 }}>
                          <button
                            className="btn btn-ghost"
                            onClick={() => toggle(cam.id)}
                            style={{ fontSize:11, padding:'4px 10px' }}
                          >
                            {cam.is_active
                              ? <><ToggleRight size={13}/> Disable</>
                              : <><ToggleLeft  size={13}/> Enable</>}
                          </button>
                          {cam.is_active && (
                            <button
                              className="btn btn-ghost"
                              onClick={() => setExpanded(cam.id)}
                              style={{ fontSize:11, padding:'4px 10px' }}
                            >
                              <Maximize2 size={13}/> Expand
                            </button>
                          )}
                          <button
                            className="btn btn-danger"
                            onClick={() => remove(cam.id)}
                            style={{ fontSize:11, padding:'4px 8px' }}
                          >
                            <Trash2 size={13}/>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}