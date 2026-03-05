import { useState } from 'react'
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

function createMultiplicationChallenge() {
  const left = Math.floor(Math.random() * 10) + 1
  const right = Math.floor(Math.random() * 10) + 1
  return {
    left,
    right,
    expected: left * right,
  }
}

function MultiplicationDialog({ challenge, answer, success, onAnswerChange, onCancel, onConfirm }) {
  return (
    <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md rounded-3xl border border-white/20 bg-gradient-to-b from-blue-500 to-purple-600 p-6 shadow-2xl">
        <p className="text-white/80 text-sm font-bold uppercase tracking-wider">Sicherheitsfrage</p>
        <h3 className="mt-1 text-white text-3xl font-black">🧠 Rechne kurz mit!</h3>

        {!success ? (
          <>
            <div className="mt-5 rounded-2xl bg-white/15 p-5 text-center">
              <p className="text-white/80 text-sm font-bold">Kleines Einmaleins</p>
              <p className="mt-1 text-white text-5xl font-black">
                {challenge.left} × {challenge.right} = ?
              </p>
            </div>

            <input
              type="number"
              inputMode="numeric"
              autoFocus
              value={answer}
              onChange={(e) => onAnswerChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onConfirm()
              }}
              placeholder="Deine Antwort"
              className="mt-4 w-full rounded-2xl border border-white/20 bg-white/90 px-4 py-3 text-center text-2xl font-black text-gray-900 outline-none focus:ring-4 focus:ring-yellow-300/50"
            />

            <div className="mt-4 flex gap-3">
              <button
                onClick={onCancel}
                className="flex-1 rounded-2xl bg-white/15 py-3 text-white font-bold hover:bg-white/25"
              >
                Abbrechen
              </button>
              <button
                onClick={onConfirm}
                className="flex-1 rounded-2xl bg-yellow-400 py-3 text-gray-900 font-extrabold hover:bg-yellow-300"
              >
                Prüfen ✓
              </button>
            </div>
          </>
        ) : (
          <div className="mt-5 rounded-2xl bg-green-500/25 border border-green-300/50 p-8 text-center">
            <div className="text-7xl leading-none">✅</div>
            <p className="mt-3 text-white text-3xl font-black">Richtig gerechnet!</p>
            <p className="mt-1 text-green-100 font-bold">Münze wird freigeschaltet …</p>
          </div>
        )}
      </div>
    </div>
  )
}

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
  }) // { id, name }
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
  const [pendingSessionStart, setPendingSessionStart] = useState(null) // { type, coins }
  const [challenge, setChallenge] = useState(null) // { left, right, expected }
  const [challengeAnswer, setChallengeAnswer] = useState('')
  const [challengeSuccess, setChallengeSuccess] = useState(false)

  const handleChildSelect = (child) => {
    setSelectedChild(child)
    setScreen('pin')
  }

  const handlePinSuccess = (token, id, name, icon) => {
    setChildToken(token)
    setChildId(id)
    const child = { id, name, icon: icon || '🐼' }
    setSelectedChild(child)
    sessionStorage.setItem('childAuth', JSON.stringify({ token, child }))
    setKioskError('')
    setScreen('overview')
  }

  const startSessionAfterChallenge = async (type, coins) => {
    try {
      const session = await startSession(childId, type, coins, childToken)
      setActiveSession(session)
      setKioskError('')
      setScreen('session')
    } catch (e) {
      setKioskError(e.message || 'Hardware konnte nicht freigeschaltet werden.')
    }
  }

  const handleChallengeCancel = () => {
    setChallenge(null)
    setPendingSessionStart(null)
    setChallengeAnswer('')
    setChallengeSuccess(false)
    setKioskError('Freischalten abgebrochen.')
  }

  const handleChallengeConfirm = async () => {
    if (!challenge || !pendingSessionStart) return

    const answer = Number.parseInt(challengeAnswer.trim(), 10)
    if (!Number.isInteger(answer) || answer !== challenge.expected) {
      setKioskError('Falsche Antwort – die Münze wurde nicht freigeschaltet.')
      return
    }

    const { type, coins } = pendingSessionStart
    setChallengeSuccess(true)
    await new Promise((resolve) => setTimeout(resolve, 900))
    setChallenge(null)
    setPendingSessionStart(null)
    setChallengeAnswer('')
    setChallengeSuccess(false)
    await startSessionAfterChallenge(type, coins)
  }

  const handleSessionStart = (existingSession, type, coins) => {
    if (existingSession) {
      // Show existing active session
      setActiveSession(existingSession)
      setScreen('session')
      return
    }

    setKioskError('')
    setPendingSessionStart({ type, coins })
    setChallenge(createMultiplicationChallenge())
    setChallengeAnswer('')
    setChallengeSuccess(false)
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
    setPendingSessionStart(null)
    setChallenge(null)
    setChallengeAnswer('')
    setChallengeSuccess(false)
    setScreen('select')
  }

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

      {challenge && (
        <MultiplicationDialog
          challenge={challenge}
          answer={challengeAnswer}
          success={challengeSuccess}
          onAnswerChange={setChallengeAnswer}
          onCancel={handleChallengeCancel}
          onConfirm={handleChallengeConfirm}
        />
      )}

      <VersionFooter />
    </div>
  )
}
