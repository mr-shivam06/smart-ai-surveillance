import { useState, useEffect } from 'react'
import { vehicleAPI } from '../services/api'
import { Car, Search, RefreshCw } from 'lucide-react'

const COLORS  = ['','red','blue','white','black','silver','green','yellow','orange','gray']
const SHAPES  = ['','sedan','suv/hatchback','van/truck','compact','motorcycle','bicycle','bus','truck']

export default function VehiclesPage() {
  const [vehicles, setVehicles] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [color,    setColor]    = useState('')
  const [shape,    setShape]    = useState('')

  const load = () => {
    setLoading(true)
    const req = color || shape
      ? vehicleAPI.search(color, shape)
      : vehicleAPI.list(200)
    req.then(r => setVehicles(r.data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const search = e => { e.preventDefault(); load() }

  return (
    <div>
      <div className="page-header">
        <div><h1>Vehicles</h1><p>Detected vehicle intelligence</p></div>
        <button className="btn btn-ghost" onClick={load}><RefreshCw size={14}/> Refresh</button>
      </div>

      {/* Search */}
      <div className="card" style={{ marginBottom:20 }}>
        <form onSubmit={search} style={{ display:'flex', gap:12, alignItems:'flex-end', flexWrap:'wrap' }}>
          <div>
            <label style={{ fontSize:12, color:'var(--text-3)', display:'block', marginBottom:6 }}>Color</label>
            <select value={color} onChange={e => setColor(e.target.value)} style={{ minWidth:140 }}>
              {COLORS.map(c => <option key={c} value={c}>{c || 'Any Color'}</option>)}
            </select>
          </div>
          <div>
            <label style={{ fontSize:12, color:'var(--text-3)', display:'block', marginBottom:6 }}>Shape Type</label>
            <select value={shape} onChange={e => setShape(e.target.value)} style={{ minWidth:160 }}>
              {SHAPES.map(s => <option key={s} value={s}>{s || 'Any Shape'}</option>)}
            </select>
          </div>
          <button type="submit" className="btn btn-primary">
            <Search size={14}/> Search
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => { setColor(''); setShape(''); }}>
            Clear
          </button>
        </form>
      </div>

      {/* Results */}
      {loading ? (
        <div style={{ display:'flex', justifyContent:'center', padding:48 }}>
          <div className="spinner"/>
        </div>
      ) : vehicles.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <Car size={32}/>
            <p style={{ marginTop:8 }}>No vehicles found</p>
            <p style={{ fontSize:12, marginTop:4 }}>Vehicles appear here when detected by the AI engine</p>
          </div>
        </div>
      ) : (
        <>
          <div style={{ fontSize:12, color:'var(--text-3)', marginBottom:12 }}>
            {vehicles.length} vehicle{vehicles.length !== 1 ? 's' : ''} found
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(260px,1fr))', gap:16 }}>
            {vehicles.map(v => (
              <div key={v.global_id} className="card">
                {/* Header */}
                <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:12 }}>
                  <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                    <div style={{
                      width:36, height:36,
                      background:'rgba(249,115,22,0.1)',
                      borderRadius:'var(--radius)',
                      display:'flex', alignItems:'center', justifyContent:'center',
                    }}>
                      <Car size={18} color="var(--orange)"/>
                    </div>
                    <div>
                      <code style={{ fontSize:13, fontWeight:700, color:'var(--teal)' }}>{v.global_id}</code>
                      <div style={{ fontSize:11, color:'var(--text-3)' }}>{v.class_name}</div>
                    </div>
                  </div>
                  <span className="badge badge-orange">{v.shape_type || 'vehicle'}</span>
                </div>

                {/* Color chip */}
                {v.color && (
                  <div style={{
                    display:'flex', alignItems:'center', gap:8,
                    padding:'6px 10px',
                    background:'var(--bg-700)',
                    borderRadius:'var(--radius)',
                    marginBottom:10,
                  }}>
                    <div style={{
                      width:14, height:14, borderRadius:3,
                      background: v.color === 'white' ? '#eee' : v.color === 'black' ? '#222' : v.color,
                      border:'1px solid rgba(255,255,255,0.2)',
                    }}/>
                    <span style={{ fontSize:12, color:'var(--text-2)', textTransform:'capitalize' }}>
                      {v.color}
                    </span>
                  </div>
                )}

                {/* Stats */}
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
                  {[
                    { label:'Frames',   value: v.frame_count },
                    { label:'Cameras',  value: Array.isArray(v.cameras) ? v.cameras.join(', ') : v.cameras },
                    { label:'First',    value: v.first_seen ? new Date(v.first_seen*1000).toLocaleTimeString() : '—' },
                    { label:'Last',     value: v.last_seen  ? new Date(v.last_seen*1000).toLocaleTimeString()  : '—' },
                  ].map(({ label, value }) => (
                    <div key={label} style={{
                      padding:'8px 10px',
                      background:'var(--bg-700)',
                      borderRadius:'var(--radius)',
                    }}>
                      <div style={{ fontSize:10, color:'var(--text-3)', marginBottom:2 }}>{label}</div>
                      <div style={{ fontSize:12, color:'var(--text-1)', fontWeight:500 }}>{value}</div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}