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
  const [kioskError, setKioskError] = useState('')
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

  const handlePinSuccess = (token, id, name, icon) => {
    setChildToken(token)
    setChildId(id)
    const child = { id, name, icon: icon || "🐼" }
    setSelectedChild(child)
    sessionStorage.setItem('childAuth', JSON.stringify({ token, child }))
    setKioskError('')
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
      setKioskError('')
      setScreen('session')
    } catch (e) {
      setKioskError(e.message || 'Hardware konnte nicht freigeschaltet werden.')
    }
  }

  const handleSessionEnd = () => {
    setActiveSession(null)
    setKioskError('')
    setScreen('overview')
  }

  const handleLogout = () => {
    sessionStorage.removeItem('childAuth')
    setSelectedChild(null)
    setChildToken(null)
    setChildId(null)
    setActiveSession(null)
    setKioskError('')
    setScreen('select')
  }

  return (
    <div className="h-screen w-screen overflow-hidden">
      {kioskError && (
        <div className="absolute left-1/2 top-4 z-50 w-[min(92vw,42rem)] -translate-x-1/2 rounded-2xl border border-red-300/40 bg-red-900/90 px-4 py-3 text-white shadow-2xl">
          <div className="flex items-start justify-between gap-3">
            <p className="text-sm font-bold">⚠️ {kioskError}</p>
            <button
              onClick={() => setKioskError('')}
              className="rounded-lg bg-white/20 px-2 py-1 text-xs font-extrabold hover:bg-white/30"
            >
              Schließen
            </button>
          </div>
        </div>
      )}
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
          onError={setKioskError}
        />
      )}

      {screen === 'session' && activeSession && (
        <ActiveSession
          session={activeSession}
          token={childToken}
          onEnd={handleSessionEnd}
          onError={setKioskError}
        />
      )}

      <VersionFooter />
    </div>
  )
}
