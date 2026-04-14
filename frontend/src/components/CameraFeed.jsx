import { useEffect, useRef, useState, useCallback } from 'react'
import { getCameraStreamUrl } from '../services/api'
import { WifiOff, Maximize2 } from 'lucide-react'

export default function CameraFeed({
  cameraId,
  name    = `Camera ${cameraId}`,
  width   = 480,
  height  = 360,
  onClick,
}) {
  const canvasRef  = useRef(null)
  const wsRef      = useRef(null)
  const prevUrlRef = useRef(null)
  const rafRef     = useRef(null)
  const mountedRef = useRef(true)
  const retryRef   = useRef(null)
  const fpsRef     = useRef({ frames: 0, last: Date.now() })

  const [status, setStatus] = useState('connecting')
  const [fps,    setFps]    = useState(0)

  // ── Draw a JPEG blob URL onto canvas ──────────────────────
  const drawFrame = useCallback((blobUrl) => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current)

    rafRef.current = requestAnimationFrame(() => {
      const canvas = canvasRef.current
      if (!canvas) { URL.revokeObjectURL(blobUrl); return }

      const ctx = canvas.getContext('2d')
      const img = new Image()

      img.onload = () => {
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

        // Revoke previous blob URL to free memory
        if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current)
        prevUrlRef.current = blobUrl

        // FPS counter
        const now = Date.now()
        fpsRef.current.frames++
        if (now - fpsRef.current.last >= 1000) {
          setFps(fpsRef.current.frames)
          fpsRef.current.frames = 0
          fpsRef.current.last   = now
        }
      }

      img.onerror = () => URL.revokeObjectURL(blobUrl)
      img.src = blobUrl
    })
  }, [])

  // ── WebSocket connect / reconnect ─────────────────────────
  useEffect(() => {
    mountedRef.current = true

    function connect() {
      if (!mountedRef.current) return

      // Close any existing connection cleanly
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
        wsRef.current = null
      }

      if (!mountedRef.current) return
      setStatus('connecting')

      const url = getCameraStreamUrl(cameraId)
      const ws  = new WebSocket(url)
      ws.binaryType = 'blob'
      wsRef.current = ws

      ws.onopen = () => {
        if (mountedRef.current) setStatus('streaming')
      }

      ws.onmessage = e => {
        // Empty blob = keepalive ping — ignore
        if (!e.data || (e.data instanceof Blob && e.data.size === 0)) return
        const blobUrl = URL.createObjectURL(e.data)
        drawFrame(blobUrl)
      }

      ws.onerror = () => {
        if (mountedRef.current) setStatus('offline')
      }

      ws.onclose = () => {
        wsRef.current = null
        if (mountedRef.current) {
          setStatus('offline')
          // Reconnect after 2s
          retryRef.current = setTimeout(connect, 2000)
        }
      }
    }

    connect()

    return () => {
      mountedRef.current = false
      clearTimeout(retryRef.current)
      if (rafRef.current)     cancelAnimationFrame(rafRef.current)
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [cameraId, drawFrame])

  // ── Colors / labels by status ────────────────────────────
  const borderColor = status === 'streaming' ? 'var(--teal)' : 'var(--border)'
  const statusLabel = {
    streaming:  '● Live',
    connecting: '◌ Connecting',
    offline:    '○ Offline',
  }[status]
  const statusColor = {
    streaming:  'var(--green)',
    connecting: 'var(--yellow)',
    offline:    'var(--red)',
  }[status]

  return (
    <div
      onClick={onClick}
      style={{
        position:   'relative',
        background: '#050505',
        borderRadius: 'var(--radius)',
        overflow:   'hidden',
        border:     `1px solid ${borderColor}`,
        cursor:     onClick ? 'pointer' : 'default',
        transition: 'border-color 0.2s',
      }}
    >
      {/* ── Canvas ── */}
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{ display:'block', width:'100%', aspectRatio:`${width}/${height}` }}
      />

      {/* ── Offline overlay ── */}
      {status === 'offline' && (
        <div style={{
          position:'absolute', inset:0,
          display:'flex', flexDirection:'column',
          alignItems:'center', justifyContent:'center',
          background:'rgba(0,0,0,0.80)', gap:10,
        }}>
          <WifiOff size={28} color="var(--red)"/>
          <span style={{ fontSize:13, color:'var(--text-2)' }}>Camera {cameraId} offline</span>
          <span style={{ fontSize:11, color:'var(--text-3)' }}>Reconnecting in 2s…</span>
        </div>
      )}

      {/* ── Connecting overlay ── */}
      {status === 'connecting' && (
        <div style={{
          position:'absolute', inset:0,
          display:'flex', flexDirection:'column',
          alignItems:'center', justifyContent:'center',
          background:'rgba(0,0,0,0.65)', gap:10,
        }}>
          <div className="spinner"/>
          <span style={{ fontSize:12, color:'var(--text-3)' }}>
            Connecting to Camera {cameraId}…
          </span>
        </div>
      )}

      {/* ── Top HUD bar ── */}
      <div style={{
        position:   'absolute', top:0, left:0, right:0,
        padding:    '6px 10px',
        background: 'linear-gradient(to bottom,rgba(0,0,0,0.75),transparent)',
        display:    'flex', alignItems:'center', justifyContent:'space-between',
        pointerEvents: 'none',
      }}>
        <span style={{ fontSize:12, fontWeight:600, color:'#fff' }}>{name}</span>
        <span style={{ fontSize:11, color: statusColor }}>
          {statusLabel}{status === 'streaming' ? `  ${fps} fps` : ''}
        </span>
      </div>

      {/* ── Expand icon ── */}
      {onClick && status === 'streaming' && (
        <div style={{
          position:'absolute', bottom:8, right:8,
          background:'rgba(0,0,0,0.55)',
          border:'1px solid rgba(255,255,255,0.15)',
          borderRadius:4, padding:'3px 5px',
          pointerEvents:'none',
        }}>
          <Maximize2 size={12} color="#fff"/>
        </div>
      )}
    </div>
  )
}