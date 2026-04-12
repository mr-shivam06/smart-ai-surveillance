import { useState, useEffect } from 'react'
import { cameraAPI } from '../services/api'
import { Camera, Plus, Trash2, ToggleLeft, ToggleRight, Wifi } from 'lucide-react'

export default function CamerasPage() {
  const [cameras,  setCameras]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [adding,   setAdding]   = useState(false)
  const [form,     setForm]     = useState({ name:'', source:'' })
  const [error,    setError]    = useState('')
  const [showForm, setShowForm] = useState(false)

  const load = () =>
    cameraAPI.list().then(r => setCameras(r.data)).finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const add = async e => {
    e.preventDefault()
    setError(''); setAdding(true)
    try {
      await cameraAPI.add(form)
      setForm({ name:'', source:'' })
      setShowForm(false)
      load()
    } catch(err) {
      setError(err.response?.data?.detail || 'Failed to add camera')
    } finally { setAdding(false) }
  }

  const remove = async id => {
    if (!confirm('Remove this camera?')) return
    await cameraAPI.delete(id)
    load()
  }

  const toggle = async id => {
    await cameraAPI.toggle(id)
    load()
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Cameras</h1>
          <p>Manage camera sources</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(s=>!s)}>
          <Plus size={15}/> Add Camera
        </button>
      </div>

      {/* Add camera form */}
      {showForm && (
        <div className="card" style={{ marginBottom:20 }}>
          <h3 style={{ fontSize:13, fontWeight:600, marginBottom:16 }}>Add New Camera</h3>
          <form onSubmit={add} style={{ display:'flex', flexDirection:'column', gap:12 }}>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:12 }}>
              <div>
                <label style={{ fontSize:12, color:'var(--text-3)', display:'block', marginBottom:6 }}>
                  Camera Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Front Door"
                  value={form.name}
                  onChange={e => setForm(f=>({...f,name:e.target.value}))}
                  required
                  style={{ width:'100%' }}
                />
              </div>
              <div>
                <label style={{ fontSize:12, color:'var(--text-3)', display:'block', marginBottom:6 }}>
                  Source
                </label>
                <input
                  type="text"
                  placeholder="0 (webcam) or http://192.168.x.x:4747/video"
                  value={form.source}
                  onChange={e => setForm(f=>({...f,source:e.target.value}))}
                  required
                  style={{ width:'100%' }}
                />
              </div>
            </div>
            {error && (
              <div style={{ color:'var(--red)', fontSize:13 }}>{error}</div>
            )}
            <div style={{ display:'flex', gap:8 }}>
              <button type="submit" className="btn btn-primary" disabled={adding}>
                {adding ? 'Adding...' : 'Add Camera'}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>
                Cancel
              </button>
            </div>
          </form>

          {/* Source hints */}
          <div style={{
            marginTop:16, padding:'12px 14px',
            background:'var(--bg-700)', borderRadius:'var(--radius)',
            fontSize:12, color:'var(--text-3)', lineHeight:1.8,
          }}>
            <strong style={{ color:'var(--text-2)' }}>Source examples:</strong><br/>
            <code style={{ color:'var(--teal)' }}>0</code> — built-in webcam<br/>
            <code style={{ color:'var(--teal)' }}>1</code> — external USB webcam<br/>
            <code style={{ color:'var(--teal)' }}>http://192.168.1.8:4747/video</code> — DroidCam (replace IP)<br/>
            <code style={{ color:'var(--teal)' }}>rtsp://user:pass@192.168.1.x/stream</code> — RTSP IP camera
          </div>
        </div>
      )}

      {/* Camera grid */}
      {loading ? (
        <div style={{ display:'flex', justifyContent:'center', padding:48 }}>
          <div className="spinner"/>
        </div>
      ) : cameras.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Camera size={32}/>
            <p style={{ marginTop:8 }}>No cameras added yet</p>
            <p style={{ fontSize:12, marginTop:4 }}>
              Click "Add Camera" to register your first camera source
            </p>
          </div>
        </div>
      ) : (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))', gap:16 }}>
          {cameras.map(cam => (
            <div key={cam.id} className="card" style={{
              borderLeft:`3px solid ${cam.is_active ? 'var(--teal)' : 'var(--border)'}`,
            }}>
              <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:12 }}>
                <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                  <div style={{
                    width:36, height:36,
                    background: cam.is_active ? 'rgba(13,217,197,0.1)' : 'var(--bg-700)',
                    borderRadius:'var(--radius)',
                    display:'flex', alignItems:'center', justifyContent:'center',
                  }}>
                    <Camera size={18} color={cam.is_active ? 'var(--teal)' : 'var(--text-3)'}/>
                  </div>
                  <div>
                    <div style={{ fontWeight:600, fontSize:14, color:'var(--text-1)' }}>{cam.name}</div>
                    <div style={{ fontSize:11, color:'var(--text-3)' }}>ID #{cam.id}</div>
                  </div>
                </div>
                <span className={`badge ${cam.is_active ? 'badge-green' : 'badge-red'}`}>
                  {cam.is_active ? '● Active' : '○ Inactive'}
                </span>
              </div>

              <div style={{
                padding:'8px 10px',
                background:'var(--bg-700)',
                borderRadius:'var(--radius)',
                marginBottom:12,
                display:'flex', alignItems:'center', gap:8,
              }}>
                <Wifi size={13} color="var(--text-3)"/>
                <code style={{ fontSize:12, color:'var(--text-2)', wordBreak:'break-all' }}>
                  {cam.source}
                </code>
              </div>

              <div style={{ display:'flex', gap:8 }}>
                <button
                  className="btn btn-ghost"
                  onClick={() => toggle(cam.id)}
                  style={{ flex:1, justifyContent:'center', fontSize:12 }}
                >
                  {cam.is_active
                    ? <><ToggleRight size={14}/> Disable</>
                    : <><ToggleLeft  size={14}/> Enable</>
                  }
                </button>
                <button
                  className="btn btn-danger"
                  onClick={() => remove(cam.id)}
                  style={{ justifyContent:'center', padding:'8px 12px' }}
                >
                  <Trash2 size={14}/>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}