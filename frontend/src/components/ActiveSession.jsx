import { useEffect, useState } from 'react'
import { endSession } from '../api.js'

function formatTime(seconds) {
  if (seconds <= 0) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function ActiveSession({ session, token, onEnd }) {
  const [remaining, setRemaining] = useState(0)
  const [confirming, setConfirming] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const calcRemaining = () => {
      const endsAt = new Date(session.ends_at)
      const now = new Date()
      return Math.max(0, Math.floor((endsAt - now) / 1000))
    }

    setRemaining(calcRemaining())
    const interval = setInterval(() => {
      const r = calcRemaining()
      setRemaining(r)
      if (r === 0) {
        clearInterval(interval)
        onEnd()
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [session.ends_at])

  const handleEnd = async () => {
    if (!confirming) {
      setConfirming(true)
      return
    }
    setLoading(true)
    try {
      await endSession(session.id, token)
      onEnd()
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  const isSwitch = session.type === 'switch'
  const totalSeconds = session.coins_used * 30 * 60
  const progress = Math.max(0, Math.min(1, remaining / totalSeconds))
  const circumference = 2 * Math.PI * 120

  // Color based on time remaining
  const urgentColor = remaining < 60 ? 'text-red-400' : remaining < 300 ? 'text-yellow-400' : 'text-green-400'
  const strokeColor = remaining < 60 ? '#f87171' : remaining < 300 ? '#facc15' : '#4ade80'

  return (
    <div className={`flex flex-col items-center justify-between h-full p-6
      bg-gradient-to-b ${isSwitch ? 'from-indigo-600 to-purple-700' : 'from-blue-600 to-cyan-700'}`}
    >
      {/* Device label */}
      <div className="text-center mt-4">
        <span className="text-8xl">{isSwitch ? '🎮' : '📺'}</span>
        <h2 className="text-white text-3xl font-black mt-2">
          {isSwitch ? 'Nintendo Switch' : 'Fernseher'}
        </h2>
        <p className="text-white/60 font-bold mt-1">
          {session.coins_used} {session.coins_used === 1 ? 'Münze' : 'Münzen'} eingelöst
        </p>
      </div>

      {/* Countdown ring */}
      <div className="relative flex items-center justify-center">
        <svg width="280" height="280" className="-rotate-90">
          <circle
            cx="140" cy="140" r="120"
            fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="12"
          />
          <circle
            cx="140" cy="140" r="120"
            fill="none" stroke={strokeColor} strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - progress)}
            style={{ transition: 'stroke-dashoffset 1s linear, stroke 1s' }}
          />
        </svg>
        <div className="absolute text-center">
          <p className="text-white/60 text-sm font-bold uppercase tracking-widest mb-1">
            Verbleibend
          </p>
          <p className={`text-6xl font-black ${urgentColor}`}>
            {formatTime(remaining)}
          </p>
        </div>
      </div>

      {/* End button */}
      <div className="w-full max-w-xs">
        {confirming ? (
          <div className="flex flex-col gap-3">
            <p className="text-white text-center font-extrabold text-lg">
              Wirklich früher beenden?
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setConfirming(false)}
                className="flex-1 py-4 bg-white/20 hover:bg-white/30 text-white font-bold rounded-2xl active:scale-95"
              >
                Weiter spielen
              </button>
              <button
                onClick={handleEnd}
                disabled={loading}
                className="flex-1 py-4 bg-red-500 hover:bg-red-400 text-white font-extrabold rounded-2xl active:scale-95 shadow-lg"
              >
                {loading ? '…' : 'Beenden'}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={handleEnd}
            className="w-full py-5 bg-white/20 hover:bg-white/30 text-white font-extrabold text-xl rounded-2xl active:scale-95 transition-all"
          >
            Früher beenden
          </button>
        )}
      </div>
    </div>
  )
}
