import axios from 'axios'

const api = axios.create({ baseURL: '' })

// ── Attach JWT token to every request ─────────────────────────
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// ── Auto-logout on 401 — prevent redirect loop ────────────────
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      if (window.location.pathname !== '/login') {
        localStorage.removeItem('token')
        localStorage.removeItem('username')
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data),

  // IMPORTANT: FastAPI OAuth2PasswordRequestForm requires
  // application/x-www-form-urlencoded, NOT JSON
  login: (username, password) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)
    return api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
  },

  me: () => api.get('/auth/me'),
}

// ── Cameras ───────────────────────────────────────────────────
export const cameraAPI = {
  list:   ()     => api.get('/cameras'),
  add:    (data) => api.post('/cameras', data),
  delete: (id)   => api.delete(`/cameras/${id}`),
  toggle: (id)   => api.patch(`/cameras/${id}/toggle`),
}

// ── Tracking ──────────────────────────────────────────────────
export const trackingAPI = {
  status:      () => api.get('/tracking/status'),
  crossCamera: () => api.get('/tracking/cross-camera'),
  reset:       () => api.post('/tracking/reset'),
}

// ── Alerts ────────────────────────────────────────────────────
export const alertAPI = {
  list:        (params) => api.get('/alerts', { params }),
  acknowledge: (id)     => api.post('/alerts/acknowledge', { alert_id: id }),
  count:       ()       => api.get('/alerts/count'),
  types:       ()       => api.get('/alerts/types'),
}

// ── Vehicles ──────────────────────────────────────────────────
export const vehicleAPI = {
  list:   (limit)        => api.get('/vehicles', { params: { limit } }),
  search: (color, shape) => api.get('/vehicles/search', {
    params: { color, shape_type: shape },
  }),
  get: (gid) => api.get(`/vehicles/${gid}`),
}

// ── Health ────────────────────────────────────────────────────
export const healthAPI = {
  check: () => api.get('/health'),
}

// ── Stream URL ────────────────────────────────────────────────
// Goes through Vite proxy → ws://localhost:8000/stream/{id}?token=...
// Use relative ws path so it works on any host
export function getCameraStreamUrl(cameraId) {
  const token    = localStorage.getItem('token') || ''
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host     = window.location.host   // e.g. localhost:5173 (Vite proxy handles it)
  return `${protocol}//${host}/stream/${cameraId}?token=${token}`
}

export default api