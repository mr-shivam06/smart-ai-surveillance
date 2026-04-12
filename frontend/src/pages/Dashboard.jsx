import { useState, useEffect } from 'react'
import { healthAPI, alertAPI, cameraAPI, trackingAPI } from '../services/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Shield, Camera, Bell, Activity, Car, AlertTriangle } from 'lucide-react'

const SEVERITY_COLOR = {
  CRITICAL: 'var(--red)',
  HIGH:     'var(--orange)',
  MEDIUM:   'var(--yellow)',
  INFO:     'var(--cyan)',
}

export default function Dashboard() {
  const [health,   setHealth]   = useState(null)
  const [alerts,   setAlerts]   = useState([])
  const [cameras,  setCameras]  = useState([])
  const [tracking, setTracking] = useState(null)
  const [loading,  setLoading]  = useState(true)

  const fetchAll = async () => {
    try {
      const [h, a, c, t] = await Promise.all([
        healthAPI.check(),
        alertAPI.list({ limit: 20 }),
        cameraAPI.list(),
        trackingAPI.status(),
      ])
      setHealth(h.data)
      setAlerts(a.data)
      setCameras(c.data)
      setTracking(t.data)
    } catch(e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, 8000)
    return () => clearInterval(id)
  }, [])

  // Alert type breakdown for chart
  const typeCounts = alerts.reduce((acc, a) => {
    const k = a.type.replace('_DETECTED','').replace('_',' ')
    acc[k] = (acc[k] || 0) + 1
    return acc
  }, {})
  const chartData = Object.entries(typeCounts).map(([name, count]) => ({ name, count }))

  const unacked = alerts.filter(a => !a.acknowledged).length
  const activeCams = cameras.filter(c => c.is_active).length

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:200 }}>
      <div className="spinner"/>
    </div>
  )

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Real-time surveillance overview</p>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <span className={`badge ${health ? 'badge-green' : 'badge-red'}`}>
            {health ? '● System Online' : '● Offline'}
          </span>
          <span style={{ fontSize:12, color:'var(--text-3)' }}>
            Auto-refreshes every 8s
          </span>
        </div>
      </div>

      {/* ── Stat cards ── */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16, marginBottom:24 }}>
        {[
          {
            label: 'Active Cameras',
            value: activeCams,
            sub:   `${cameras.length} total registered`,
            icon:  Camera,
            color: 'var(--teal)',
          },
          {
            label: 'Tracked IDs',
            value: health?.global_ids ?? '—',
            sub:   `${health?.cross_cam ?? 0} cross-camera`,
            icon:  Activity,
            color: 'var(--cyan)',
          },
          {
            label: 'Unacked Alerts',
            value: unacked,
            sub:   `${alerts.length} total recent`,
            icon:  Bell,
            color: unacked > 0 ? 'var(--red)' : 'var(--green)',
          },
          {
            label: 'ReID Backend',
            value: tracking?.reid_backend ?? '—',
            sub:   `${tracking?.cross_cam_matches ?? 0} cross-cam matches`,
            icon:  Shield,
            color: 'var(--purple)',
          },
        ].map(({ label, value, sub, icon: Icon, color }) => (
          <div key={label} className="stat-card">
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10 }}>
              <div className="label">{label}</div>
              <Icon size={16} color={color}/>
            </div>
            <div className="value" style={{ color }}>{value}</div>
            <div className="sub">{sub}</div>
          </div>
        ))}
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:20, marginBottom:24 }}>

        {/* Alert type chart */}
        <div className="card">
          <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:16 }}>
            Alert Breakdown
          </h3>
          {chartData.length === 0 ? (
            <div className="empty-state">
              <Bell size={28}/>
              <p>No alerts yet</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData} barSize={24}>
                <XAxis dataKey="name" tick={{ fill:'var(--text-3)', fontSize:11 }} axisLine={false} tickLine={false}/>
                <YAxis tick={{ fill:'var(--text-3)', fontSize:11 }} axisLine={false} tickLine={false}/>
                <Tooltip
                  contentStyle={{ background:'var(--bg-700)', border:'1px solid var(--border)', borderRadius:8 }}
                  labelStyle={{ color:'var(--text-1)' }}
                  itemStyle={{ color:'var(--teal)' }}
                />
                <Bar dataKey="count" radius={[4,4,0,0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={['var(--red)','var(--orange)','var(--yellow)','var(--cyan)','var(--purple)','var(--teal)'][i % 6]}/>
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent alerts */}
        <div className="card">
          <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:16 }}>
            Recent Alerts
          </h3>
          {alerts.length === 0 ? (
            <div className="empty-state">
              <AlertTriangle size={28}/>
              <p>No alerts</p>
            </div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:8, maxHeight:200, overflowY:'auto' }}>
              {alerts.slice(0,8).map(a => (
                <div key={a.alert_id} style={{
                  display:'flex', alignItems:'flex-start', gap:10,
                  padding:'8px 10px',
                  background:'var(--bg-700)',
                  borderRadius:'var(--radius)',
                  borderLeft:`3px solid ${SEVERITY_COLOR[a.severity] || 'var(--border)'}`,
                  opacity: a.acknowledged ? 0.5 : 1,
                }}>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:12, fontWeight:600, color:'var(--text-1)' }}>
                      {a.type.replace(/_/g,' ')}
                    </div>
                    <div style={{ fontSize:11, color:'var(--text-3)', marginTop:2 }}>
                      Cam {a.camera_id} · {new Date(a.timestamp*1000).toLocaleTimeString()}
                    </div>
                  </div>
                  <span className={`badge badge-${a.severity === 'CRITICAL' ? 'red' : a.severity === 'HIGH' ? 'orange' : a.severity === 'MEDIUM' ? 'yellow' : 'cyan'}`}>
                    {a.severity}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Camera status table */}
      <div className="card">
        <h3 style={{ fontSize:13, fontWeight:600, color:'var(--text-2)', marginBottom:16 }}>
          Camera Status
        </h3>
        {cameras.length === 0 ? (
          <div className="empty-state">
            <Camera size={28}/>
            <p>No cameras added yet — go to Cameras page to add one</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>Name</th><th>Source</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {cameras.map(cam => (
                  <tr key={cam.id}>
                    <td style={{ color:'var(--text-3)' }}>#{cam.id}</td>
                    <td style={{ fontWeight:500, color:'var(--text-1)' }}>{cam.name}</td>
                    <td style={{ fontFamily:'monospace', fontSize:12 }}>{cam.source}</td>
                    <td>
                      <span className={`badge ${cam.is_active ? 'badge-green' : 'badge-red'}`}>
                        {cam.is_active ? 'Active' : 'Inactive'}
                      </span>
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