import { useEffect, useState } from 'react'
import { getChildStatus, getActiveSession } from '../api.js'

function CoinRow({ label, emoji, coins, max, onStart, disabled }) {
  const [showSelect, setShowSelect] = useState(false)
  const [selected, setSelected] = useState(1)

  const handleStart = () => {
    if (coins < 1) return
    setShowSelect(true)
    setSelected(1)
  }

  const handleConfirm = () => {
    setShowSelect(false)
    onStart(selected)
  }

  return (
    <div className="bg-white/15 rounded-3xl p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-white text-2xl font-extrabold">
          {emoji} {label}
        </span>
        <span className="text-white/70 text-lg font-bold">
          {coins} / {max}
        </span>
      </div>

      {/* Coin icons */}
      <div className="flex flex-wrap gap-2 min-h-10">
        {Array.from({ length: coins }).map((_, i) => (
          <span key={i} className="text-3xl">🪙</span>
        ))}
        {coins === 0 && (
          <span className="text-white/40 text-lg font-bold italic">Keine Münzen</span>
        )}
      </div>

      {!showSelect ? (
        <button
          onClick={handleStart}
          disabled={disabled || coins < 1}
          className={`py-4 text-xl font-extrabold rounded-2xl transition-all active:scale-95 shadow
            ${coins >= 1 && !disabled
              ? 'bg-yellow-400 hover:bg-yellow-300 text-gray-900'
              : 'bg-white/10 text-white/30 cursor-not-allowed'
            }`}
        >
          {coins < 1 ? 'Keine Münzen' : disabled ? 'Läuft gerade…' : 'Starten 🚀'}
        </button>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-white font-bold text-center">Wie viele Münzen? (je 30 Min)</p>
          <div className="flex items-center justify-center gap-4">
            <button
              onClick={() => setSelected((s) => Math.max(1, s - 1))}
              className="bg-white/20 hover:bg-white/30 text-white text-3xl font-bold w-14 h-14 rounded-2xl active:scale-95"
            >
              −
            </button>
            <span className="text-white text-4xl font-black w-20 text-center">
              {selected}
            </span>
            <button
              onClick={() => setSelected((s) => Math.min(coins, s + 1))}
              className="bg-white/20 hover:bg-white/30 text-white text-3xl font-bold w-14 h-14 rounded-2xl active:scale-95"
            >
              +
            </button>
          </div>
          <p className="text-white/60 text-center text-sm font-bold">
            = {selected * 30} Minuten
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => setShowSelect(false)}
              className="flex-1 py-3 bg-white/10 hover:bg-white/20 text-white font-bold rounded-2xl active:scale-95"
            >
              Abbrechen
            </button>
            <button
              onClick={handleConfirm}
              className="flex-1 py-3 bg-green-400 hover:bg-green-300 text-white font-extrabold rounded-2xl active:scale-95 shadow"
            >
              Los! ✓
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function CoinOverview({ childId, token, onSessionStart, onLogout, sessionError }) {
  const [status, setStatus] = useState(null)
  const [activeSession, setActiveSession] = useState(null)
  const [error, setError] = useState('')

  const load = async () => {
    try {
      const [st, sess] = await Promise.all([
        getChildStatus(childId, token),
        getActiveSession(childId, token),
      ])
      setStatus(st)
      setActiveSession(sess)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    load()
  }, [childId, token])

  if (!status) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 h-full bg-gradient-to-b from-blue-500 to-purple-600">
        {error ? (
          <>
            <p className="text-red-300 text-2xl font-bold">{error}</p>
            <button
              onClick={onLogout}
              className="text-white/70 hover:text-white font-bold text-lg underline"
            >
              Zurück
            </button>
          </>
        ) : (
          <p className="text-white text-2xl font-bold animate-pulse">Lädt…</p>
        )}
      </div>
    )
  }

  const hasActiveSession = activeSession && activeSession.status === 'active'

  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-blue-500 to-purple-600">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-6 pb-4">
        <div>
          <p className="text-white/70 text-sm font-bold uppercase tracking-wider">Hallo</p>
          <h2 className="text-white text-3xl font-black">{status.name}</h2>
        </div>
        <button
          onClick={onLogout}
          className="text-white/50 hover:text-white/80 font-bold text-lg transition-colors px-4 py-2"
        >
          Abmelden
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pb-6 flex flex-col gap-4">
        {error && (
          <p className="text-red-300 font-bold">{error}</p>
        )}
        {sessionError && (
          <p className="text-red-300 font-extrabold text-center bg-red-900/40 rounded-2xl px-4 py-3">{sessionError}</p>
        )}

        {hasActiveSession && (
          <div className="bg-green-400/30 border-2 border-green-400/50 rounded-3xl p-4 text-center">
            <p className="text-white font-extrabold text-xl">
              Session läuft: {activeSession.type === 'switch' ? '🎮 Switch' : '📺 TV'}
            </p>
            <button
              onClick={() => onSessionStart(activeSession)}
              className="mt-2 text-yellow-300 font-bold underline"
            >
              Zur laufenden Session →
            </button>
          </div>
        )}

        {/* Time window info */}
        {(() => {
          const periods = status.is_weekend_or_holiday
            ? status.weekend_periods
            : status.allowed_periods
          const label = periods.map((p) => `${p.von}–${p.bis} Uhr`).join('  •  ')
          return (
            <p className={`text-sm font-bold text-center ${status.is_weekend_or_holiday ? 'text-white/70' : 'text-white/60'}`}>
              {status.is_weekend_or_holiday ? '🎉 ' : ''}{label}
            </p>
          )
        })()}

        <CoinRow
          label="Nintendo Switch"
          emoji="🎮"
          coins={status.switch_coins}
          max={status.switch_coins_max}
          disabled={hasActiveSession}
          onStart={(coins) => onSessionStart(null, 'switch', coins)}
        />

        <CoinRow
          label="Fernseher"
          emoji="📺"
          coins={status.tv_coins}
          max={status.tv_coins_max}
          disabled={hasActiveSession}
          onStart={(coins) => onSessionStart(null, 'tv', coins)}
        />
      </div>
    </div>
  )
}
