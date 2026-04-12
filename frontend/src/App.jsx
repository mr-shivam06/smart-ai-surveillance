import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import LoginPage    from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import Layout       from './components/Layout'
import Dashboard    from './pages/Dashboard'
import CamerasPage  from './pages/CamerasPage'
import AlertsPage   from './pages/AlertsPage'
import VehiclesPage from './pages/VehiclesPage'
import TrackingPage from './pages/TrackingPage'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100vh'}}><div className="spinner"/></div>
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login"    element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/" element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }>
            <Route index              element={<Dashboard />} />
            <Route path="cameras"     element={<CamerasPage />} />
            <Route path="alerts"      element={<AlertsPage />} />
            <Route path="vehicles"    element={<VehiclesPage />} />
            <Route path="tracking"    element={<TrackingPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}