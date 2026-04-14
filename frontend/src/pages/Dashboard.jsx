import { useState, useEffect } from 'react'
import { healthAPI, alertAPI, cameraAPI, trackingAPI } from '../services/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Shield, Camera, Bell, Activity, AlertTriangle, Video } from 'lucide-react'

const SEVERITY_COLOR = {
  CRITICAL: 'var(--red)',
  HIGH: 'var(--orange)',
  MEDIUM: 'var(--yellow)',
  INFO: 'var(--cyan)',
}

export default function Dashboard() {
  const [health, setHealth] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [cameras, setCameras] = useState([])
  const [tracking, setTracking] = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchAll = async () => {
    setLoading(true)
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

    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  // ✅ ONLY RUN ONCE (NO POLLING)
  useEffect(() => {
    fetchAll()
  }, [])

  const typeCounts = alerts.reduce((acc, a) => {
    const k = a.type.replace('DETECTED', '').replace(/_/g, ' ')
    acc[k] = (acc[k] || 0) + 1
    return acc
  }, {})

  const chartData = Object.entries(typeCounts).map(([name, count]) => ({ name, count }))
  const unacked = alerts.filter(a => !a.acknowledged).length
  const activeCams = cameras.filter(c => c.is_active).length
  const streaming = health?.streaming_cams?.length ?? 0

  // ✅ FIX loading UI
  if (loading) {
    return <div>Loading dashboard...</div>
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>Dashboard</h2>

      {/* ✅ MANUAL REFRESH */}
      <button onClick={fetchAll} style={{ marginBottom: 10 }}>
        Refresh Dashboard
      </button>

      <div>
        {activeCams} active cameras · {streaming} streaming
      </div>

      <div>
        Alerts: {alerts.length} | Unacknowledged: {unacked}
      </div>

      <div>
        Tracking IDs: {tracking?.total_identities || 0}
      </div>
    </div>
  )
}