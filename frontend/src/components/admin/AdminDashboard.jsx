import { useEffect, useState, useCallback } from 'react'
import {
  adminGetChildren, adminGetSessions, adminGetCoinLog,
  adminCancelSession, adminDeleteChild, adminAdjustCoins,
  adminCreateChild, adminUpdateChild, adminGetMockStatus
} from '../../api.js'
import ChildForm from './ChildForm.jsx'
import CoinLogView from './CoinLogView.jsx'

const TABS = ['Kinder', 'Sessions', 'Münz-Log']

function MockStatusBar({ token }) {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    const load = () =>
      adminGetMockStatus(token)
        .then(setStatus)
        .catch(() => setStatus(null)) // Not in mock mode → hide bar
    load()
    const iv = setInterval(load, 3000)
    return () => clearInterval(iv)
  }, [token])

  if (!status) return null

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-yellow-500/20 border-b border-yellow-500/40 text-xs font-bold">
      <span className="text-yellow-400 uppercase tracking-widest">🧪 Simulations-Modus</span>
      <span className={status.tv_unlocked ? 'text-green-400' : 'text-gray-400'}>
        📺 TV: {status.tv_unlocked ? 'freigegeben ✅' : 'gesperrt 🔒'}
      </span>
      <span className={status.switch_unlocked ? 'text-green-400' : 'text-gray-400'}>
        🎮 Switch: {status.switch_unlocked ? `${status.switch_minutes} Min ✅` : 'gesperrt 🔒'}
      </span>
    </div>
  )
}

export default function AdminDashboard({ token, onLogout }) {
  const [tab, setTab] = useState('Kinder')
  const [children, setChildren] = useState([])
  const [sessions, setSessions] = useState([])
  const [coinLog, setCoinLog] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [editChild, setEditChild] = useState(null) // null | 'new' | child object
  const [coinLogChild, setCoinLogChild] = useState(null)

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      if (tab === 'Kinder') {
        setChildren(await adminGetChildren(token))
      } else if (tab === 'Sessions') {
        setSessions(await adminGetSessions(token))
      } else if (tab === 'Münz-Log') {
        setCoinLog(await adminGetCoinLog(coinLogChild?.id || null, token))
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadData() }, [tab, coinLogChild])

  const handleCancelSession = async (id) => {
    if (!confirm('Session wirklich beenden?')) return
    try {
      await adminCancelSession(id, token)
      setSessions((s) => s.map((x) => x.id === id ? { ...x, status: 'cancelled' } : x))
    } catch (e) {
      alert(e.message)
    }
  }

  const handleDeleteChild = async (id, name) => {
    if (!confirm(`${name} wirklich löschen?`)) return
    try {
      await adminDeleteChild(id, token)
      setChildren((c) => c.filter((x) => x.id !== id))
    } catch (e) {
      alert(e.message)
    }
  }

  const handleQuickAdjust = async (child, type, delta) => {
    try {
      await adminAdjustCoins(child.id, type, delta, 'admin_adjust', token)
      setChildren((c) =>
        c.map((x) =>
          x.id === child.id
            ? { ...x, [`${type}_coins`]: Math.max(0, Math.min(x[`${type}_coins`] + delta, x[`${type}_coins_max`])) }
            : x
        )
      )
    } catch (e) {
      alert(e.message)
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-900 text-white">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-gray-800 border-b border-gray-700">
        <h1 className="text-xl font-black">⚙️ Eltern-Bereich</h1>
        <button onClick={onLogout} className="text-gray-400 hover:text-white text-lg font-bold px-4 py-2">
          Abmelden
        </button>
      </div>

      <MockStatusBar token={token} />

      {/* Tabs */}
      <div className="flex border-b border-gray-700">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-3 text-sm font-bold transition-colors ${
              tab === t ? 'text-yellow-400 border-b-2 border-yellow-400' : 'text-gray-400 hover:text-white'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {error && <p className="text-red-400 text-sm font-bold px-6 py-2">{error}</p>}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading && <p className="text-gray-400 text-center py-8">Lädt…</p>}

        {/* --- Kinder --- */}
        {!loading && tab === 'Kinder' && (
          <div className="flex flex-col gap-3">
            <button
              onClick={() => setEditChild('new')}
              className="w-full py-3 bg-yellow-400 hover:bg-yellow-300 text-gray-900 font-extrabold rounded-2xl active:scale-95"
            >
              + Kind hinzufügen
            </button>

            {children.map((child) => (
              <div key={child.id} className="bg-gray-800 rounded-2xl p-4 flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-extrabold">{child.name}</h3>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setEditChild(child)}
                      className="text-blue-400 hover:text-blue-300 text-sm font-bold"
                    >
                      Bearbeiten
                    </button>
                    <button
                      onClick={() => handleDeleteChild(child.id, child.name)}
                      className="text-red-400 hover:text-red-300 text-sm font-bold"
                    >
                      Löschen
                    </button>
                  </div>
                </div>

                <p className="text-gray-400 text-xs">
                  Zeit: {child.allowed_from} – {child.allowed_until} Uhr
                </p>

                {/* Switch coins */}
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold w-24">🎮 Switch</span>
                  <button onClick={() => handleQuickAdjust(child, 'switch', -1)}
                    className="bg-gray-700 hover:bg-gray-600 w-8 h-8 rounded-xl font-bold active:scale-90">−</button>
                  <span className="font-extrabold w-16 text-center">
                    {child.switch_coins} / {child.switch_coins_max}
                  </span>
                  <button onClick={() => handleQuickAdjust(child, 'switch', 1)}
                    className="bg-gray-700 hover:bg-gray-600 w-8 h-8 rounded-xl font-bold active:scale-90">+</button>
                  <span className="text-gray-500 text-xs ml-2">+{child.switch_coins_weekly}/Wo</span>
                </div>

                {/* TV coins */}
                <div className="flex items-center gap-3">
                  <span className="text-sm font-bold w-24">📺 TV</span>
                  <button onClick={() => handleQuickAdjust(child, 'tv', -1)}
                    className="bg-gray-700 hover:bg-gray-600 w-8 h-8 rounded-xl font-bold active:scale-90">−</button>
                  <span className="font-extrabold w-16 text-center">
                    {child.tv_coins} / {child.tv_coins_max}
                  </span>
                  <button onClick={() => handleQuickAdjust(child, 'tv', 1)}
                    className="bg-gray-700 hover:bg-gray-600 w-8 h-8 rounded-xl font-bold active:scale-90">+</button>
                  <span className="text-gray-500 text-xs ml-2">+{child.tv_coins_weekly}/Wo</span>
                </div>

                <button
                  onClick={() => { setCoinLogChild(child); setTab('Münz-Log') }}
                  className="text-gray-400 hover:text-white text-xs font-bold text-left"
                >
                  Münz-Verlauf anzeigen →
                </button>
              </div>
            ))}
          </div>
        )}

        {/* --- Sessions --- */}
        {!loading && tab === 'Sessions' && (
          <div className="flex flex-col gap-3">
            <button onClick={loadData} className="text-gray-400 hover:text-white text-sm font-bold text-right mb-2">
              ↻ Aktualisieren
            </button>
            {sessions.length === 0 && (
              <p className="text-gray-500 text-center py-8">Keine Sessions</p>
            )}
            {sessions.map((s) => (
              <div key={s.id} className={`rounded-2xl p-4 ${
                s.status === 'active' ? 'bg-green-900/40 border border-green-700' : 'bg-gray-800'
              }`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-extrabold">
                    {s.child_name} – {s.type === 'switch' ? '🎮' : '📺'} {s.type}
                  </span>
                  <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                    s.status === 'active' ? 'bg-green-500 text-white' :
                    s.status === 'completed' ? 'bg-gray-600 text-gray-300' :
                    'bg-red-600 text-white'
                  }`}>
                    {s.status === 'active' ? 'Aktiv' : s.status === 'completed' ? 'Abgeschlossen' : 'Abgebrochen'}
                  </span>
                </div>
                <p className="text-gray-400 text-xs">
                  Start: {new Date(s.started_at).toLocaleString('de-DE')}
                </p>
                <p className="text-gray-400 text-xs">
                  Ende: {new Date(s.ends_at).toLocaleString('de-DE')}
                </p>
                <p className="text-gray-400 text-xs">{s.coins_used} Münze(n) eingesetzt</p>
                {s.status === 'active' && (
                  <button
                    onClick={() => handleCancelSession(s.id)}
                    className="mt-2 text-red-400 hover:text-red-300 text-sm font-bold"
                  >
                    Session beenden
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* --- Münz-Log --- */}
        {!loading && tab === 'Münz-Log' && (
          <div className="flex flex-col gap-3">
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setCoinLogChild(null)}
                className={`px-3 py-1 rounded-full text-sm font-bold ${
                  !coinLogChild ? 'bg-yellow-400 text-gray-900' : 'bg-gray-700 text-gray-300'
                }`}
              >
                Alle
              </button>
              {children.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setCoinLogChild(c)}
                  className={`px-3 py-1 rounded-full text-sm font-bold ${
                    coinLogChild?.id === c.id ? 'bg-yellow-400 text-gray-900' : 'bg-gray-700 text-gray-300'
                  }`}
                >
                  {c.name}
                </button>
              ))}
            </div>
            {coinLog.length === 0 && (
              <p className="text-gray-500 text-center py-8">Kein Verlauf</p>
            )}
            {coinLog.map((entry) => (
              <div key={entry.id} className="bg-gray-800 rounded-xl p-3 flex justify-between items-center">
                <div>
                  <p className="font-bold text-sm">
                    {entry.child_name} – {entry.type === 'switch' ? '🎮' : '📺'}
                  </p>
                  <p className="text-gray-400 text-xs">
                    {entry.reason === 'weekly_refill' ? 'Wochenaufladung' :
                     entry.reason === 'session' ? 'Session' : 'Admin-Anpassung'}
                  </p>
                  <p className="text-gray-500 text-xs">
                    {new Date(entry.created_at).toLocaleString('de-DE')}
                  </p>
                </div>
                <span className={`text-xl font-black ${entry.delta > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {entry.delta > 0 ? '+' : ''}{entry.delta}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Child form modal */}
      {editChild && (
        <ChildForm
          child={editChild === 'new' ? null : editChild}
          token={token}
          onSave={async (data) => {
            try {
              if (editChild === 'new') {
                await adminCreateChild(data, token)
              } else {
                await adminUpdateChild(editChild.id, data, token)
              }
              setEditChild(null)
              loadData()
            } catch (e) {
              alert(e.message)
            }
          }}
          onClose={() => setEditChild(null)}
        />
      )}
    </div>
  )
}
