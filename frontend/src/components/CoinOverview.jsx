import { useEffect, useState } from 'react'
import { changeChildPin, getChildStatus, getActiveSession, setChildIcon } from '../api.js'

const ANIMAL_ICONS = ['🦁', '🐻', '🐼', '🦊', '🐨', '🐯', '🦄', '🐸', '🐧', '🦋', '🐙', '🐵']

function formatTimeShort(seconds) {
  if (seconds <= 0) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

function SessionBanner({ session, onClick }) {
  const [remaining, setRemaining] = useState(0)

  useEffect(() => {
    const calc = () => {
      const endsAt = new Date(session.ends_at)
      return Math.max(0, Math.floor((endsAt - new Date()) / 1000))
    }
    setRemaining(calc())
    const interval = setInterval(() => setRemaining(calc()), 1000)
    return () => clearInterval(interval)
  }, [session.ends_at])

  const totalSeconds = session.coins_used * 30 * 60
  const progress = Math.max(0, Math.min(1, remaining / totalSeconds))
  const r = 33
  const circumference = 2 * Math.PI * r
  const strokeColor = remaining < 60 ? '#f87171' : remaining < 300 ? '#facc15' : '#4ade80'
  const timeColor = remaining < 60 ? 'text-red-400' : remaining < 300 ? 'text-yellow-300' : 'text-green-400'

  const endsAt = new Date(session.ends_at).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
  const minuteNow = Math.min(session.coins_used * 30, Math.floor((totalSeconds - remaining) / 60) + 1)
  const totalMinutes = session.coins_used * 30

  return (
    <div className="bg-green-400/30 border-2 border-green-400/50 rounded-3xl p-4">
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <p className="text-white font-extrabold text-xl">
            {session.type === 'switch' ? '🎮 Switch' : '📺 TV'} läuft
          </p>
          <p className="text-white/70 text-sm font-bold mt-1">
            Minute {minuteNow} von {totalMinutes}
          </p>
          <p className="text-white/70 text-sm font-bold">
            bis {endsAt} Uhr
          </p>
        </div>
        <div className="relative flex-shrink-0 flex items-center justify-center">
          <svg width="80" height="80" className="-rotate-90">
            <circle cx="40" cy="40" r={r} fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="7" />
            <circle
              cx="40" cy="40" r={r}
              fill="none" stroke={strokeColor} strokeWidth="7"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - progress)}
              style={{ transition: 'stroke-dashoffset 1s linear, stroke 1s' }}
            />
          </svg>
          <p className={`absolute text-xs font-black leading-none ${timeColor}`}>
            {formatTimeShort(remaining)}
          </p>
        </div>
      </div>
      <button
        onClick={onClick}
        className="mt-3 w-full text-center text-yellow-300 font-bold underline"
      >
        Zur laufenden Session →
      </button>
    </div>
  )
}

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

function ChildSettings({ childId, token, status, onClose, onSaved, onError }) {
  const [currentPin, setCurrentPin] = useState('')
  const [newPin, setNewPin] = useState('')
  const [saving, setSaving] = useState(false)

  return (
    <div className="absolute inset-0 bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl p-5 w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <p className="text-gray-900 text-xl font-black">⚙️ Einstellungen</p>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700 font-bold">Schließen</button>
        </div>

        <div className="mb-6">
          <p className="text-gray-900 text-lg font-bold mb-2">Icon wählen</p>
          <div className="grid grid-cols-6 gap-2">
            {ANIMAL_ICONS.map((icon) => (
              <button
                key={icon}
                onClick={async () => {
                  try {
                    await setChildIcon(childId, icon, token)
                    onSaved({ icon })
                  } catch (e) {
                    onError?.(e.message || 'Icon konnte nicht gespeichert werden.')
                  }
                }}
                className={`text-3xl rounded-xl p-2 border ${status.icon === icon ? 'bg-yellow-100 border-yellow-400' : 'bg-gray-100 hover:bg-gray-200 border-transparent'}`}
              >
                {icon}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-gray-900 text-lg font-bold mb-2">PIN ändern</p>
          <div className="flex flex-col gap-2">
            <input
              type="password"
              inputMode="numeric"
              placeholder="Aktuelle PIN"
              value={currentPin}
              onChange={(e) => setCurrentPin(e.target.value)}
              className="rounded-xl border border-gray-300 px-3 py-2"
            />
            <input
              type="password"
              inputMode="numeric"
              placeholder="Neue PIN"
              value={newPin}
              onChange={(e) => setNewPin(e.target.value)}
              className="rounded-xl border border-gray-300 px-3 py-2"
            />
            <button
              disabled={saving}
              onClick={async () => {
                setSaving(true)
                try {
                  await changeChildPin(childId, currentPin, newPin, token)
                  setCurrentPin('')
                  setNewPin('')
                  alert('PIN aktualisiert')
                } catch (e) {
                  onError?.(e.message || 'PIN konnte nicht geändert werden.')
                } finally {
                  setSaving(false)
                }
              }}
              className="mt-1 py-2 bg-gray-900 text-white rounded-xl font-bold disabled:opacity-60"
            >
              PIN speichern
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function CoinOverview({ childId, token, onSessionStart, onLogout, onError }) {
  const [status, setStatus] = useState(null)
  const [activeSession, setActiveSession] = useState(null)
  const [error, setError] = useState('')
  const [showSettings, setShowSettings] = useState(false)

  const load = async () => {
    try {
      const [st, sess] = await Promise.all([
        getChildStatus(childId, token),
        getActiveSession(childId, token),
      ])
      setStatus(st)
      setActiveSession(sess)
      onError?.('')
    } catch (e) {
      setError(e.message)
      onError?.(e.message || 'Status konnte nicht geladen werden.')
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
      <div className="flex items-center justify-between px-6 pt-6 pb-4">
        <div>
          <p className="text-white/70 text-sm font-bold uppercase tracking-wider">Hallo</p>
          <h2 className="text-white text-3xl font-black">{status.icon || '🐼'} {status.name}</h2>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowSettings(true)}
            className="text-white/80 hover:text-white font-bold text-2xl transition-colors px-3 py-2"
            title="Einstellungen"
          >
            ⚙️
          </button>
          <button
            onClick={onLogout}
            className="text-white/50 hover:text-white/80 font-bold text-lg transition-colors px-4 py-2"
          >
            Abmelden
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pb-6 flex flex-col gap-4">
        {error && (
          <p className="text-red-300 font-bold">{error}</p>
        )}

        {hasActiveSession && (
          <SessionBanner session={activeSession} onClick={() => onSessionStart(activeSession)} />
        )}

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

      {showSettings && (
        <ChildSettings
          childId={childId}
          token={token}
          status={status}
          onClose={() => setShowSettings(false)}
          onSaved={(changes) => setStatus((s) => ({ ...s, ...changes }))}
          onError={(msg) => {
            setError(msg)
            onError?.(msg)
          }}
        />
      )}
    </div>
  )
}
