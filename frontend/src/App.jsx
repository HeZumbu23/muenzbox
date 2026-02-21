import { useState, useEffect } from 'react'
import ChildSelect from './components/ChildSelect.jsx'
import PinInput from './components/PinInput.jsx'
import CoinOverview from './components/CoinOverview.jsx'
import ActiveSession from './components/ActiveSession.jsx'
import AdminLogin from './components/admin/AdminLogin.jsx'
import AdminDashboard from './components/admin/AdminDashboard.jsx'
import { startSession } from './api.js'

// Determine mode from URL path
const IS_ADMIN = window.location.pathname.startsWith('/eltern')

export default function App() {
  // Admin state
  const [adminToken, setAdminToken] = useState(() => sessionStorage.getItem('adminToken'))

  // Children kiosk state
  const [selectedChild, setSelectedChild] = useState(null)  // { id, name }
  const [childToken, setChildToken] = useState(null)
  const [childId, setChildId] = useState(null)
  const [activeSession, setActiveSession] = useState(null)
  const [screen, setScreen] = useState('select') // select | pin | overview | session

  // --- Admin mode ---
  if (IS_ADMIN) {
    if (!adminToken) {
      return (
        <AdminLogin
          onSuccess={(token) => {
            sessionStorage.setItem('adminToken', token)
            setAdminToken(token)
          }}
        />
      )
    }
    return (
      <AdminDashboard
        token={adminToken}
        onLogout={() => {
          sessionStorage.removeItem('adminToken')
          setAdminToken(null)
        }}
      />
    )
  }

  // --- Children kiosk mode ---

  const handleChildSelect = (child) => {
    setSelectedChild(child)
    setScreen('pin')
  }

  const handlePinSuccess = (token, id, name) => {
    setChildToken(token)
    setChildId(id)
    setSelectedChild((c) => ({ ...c, name }))
    setScreen('overview')
  }

  const handleSessionStart = async (existingSession, type, coins) => {
    if (existingSession) {
      // Show existing active session
      setActiveSession(existingSession)
      setScreen('session')
      return
    }
    // Start new session
    try {
      const session = await startSession(childId, type, coins, childToken)
      setActiveSession(session)
      setScreen('session')
    } catch (e) {
      alert(e.message)
    }
  }

  const handleSessionEnd = () => {
    setActiveSession(null)
    setScreen('overview')
  }

  const handleLogout = () => {
    setSelectedChild(null)
    setChildToken(null)
    setChildId(null)
    setActiveSession(null)
    setScreen('select')
  }

  return (
    <div className="h-screen w-screen overflow-hidden">
      {screen === 'select' && (
        <ChildSelect onSelect={handleChildSelect} />
      )}

      {screen === 'pin' && selectedChild && (
        <PinInput
          child={selectedChild}
          onSuccess={handlePinSuccess}
          onBack={() => setScreen('select')}
        />
      )}

      {screen === 'overview' && childToken && (
        <CoinOverview
          childId={childId}
          token={childToken}
          onSessionStart={handleSessionStart}
          onLogout={handleLogout}
        />
      )}

      {screen === 'session' && activeSession && (
        <ActiveSession
          session={activeSession}
          token={childToken}
          onEnd={handleSessionEnd}
        />
      )}
    </div>
  )
}
