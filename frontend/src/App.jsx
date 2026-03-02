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

const buildNumber = import.meta.env.VITE_BUILD_NUMBER
const commitMsg = import.meta.env.VITE_COMMIT_MSG

function VersionFooter() {
  return (
    <div className="fixed bottom-0 left-0 right-0 flex justify-center pb-1 pointer-events-none select-none">
      <span className="bg-white/70 text-gray-900 text-xs font-mono px-2 py-0.5 rounded-full">
        #{buildNumber ?? 'dev'}{commitMsg ? ` · ${commitMsg}` : ''}
      </span>
    </div>
  )
}

export default function App() {
  // Admin state
  const [adminToken, setAdminToken] = useState(() => sessionStorage.getItem('adminToken'))

  // Children kiosk state
  const [selectedChild, setSelectedChild] = useState(() => {
    const raw = sessionStorage.getItem('childAuth')
    if (!raw) return null
    try {
      const data = JSON.parse(raw)
      return data.child ? { id: data.child.id, name: data.child.name } : null
    } catch { return null }
  })  // { id, name }
  const [childToken, setChildToken] = useState(() => {
    const raw = sessionStorage.getItem('childAuth')
    if (!raw) return null
    try { return JSON.parse(raw).token ?? null } catch { return null }
  })
  const [childId, setChildId] = useState(() => {
    const raw = sessionStorage.getItem('childAuth')
    if (!raw) return null
    try { return JSON.parse(raw).child?.id ?? null } catch { return null }
  })
  const [activeSession, setActiveSession] = useState(null)
  const [screen, setScreen] = useState(() => (sessionStorage.getItem('childAuth') ? 'overview' : 'select')) // select | pin | overview | session

  // --- Admin mode ---
  if (IS_ADMIN) {
    if (!adminToken) {
      return (
        <>
          <AdminLogin
            onSuccess={(token) => {
              sessionStorage.setItem('adminToken', token)
              setAdminToken(token)
            }}
          />
          <VersionFooter />
        </>
      )
    }
    return (
      <>
        <AdminDashboard
          token={adminToken}
          onLogout={() => {
            sessionStorage.removeItem('adminToken')
            setAdminToken(null)
          }}
        />
        <VersionFooter />
      </>
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
    const child = { id, name }
    setSelectedChild(child)
    sessionStorage.setItem('childAuth', JSON.stringify({ token, child }))
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
    sessionStorage.removeItem('childAuth')
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

      <VersionFooter />
    </div>
  )
}
