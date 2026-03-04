import { useEffect, useRef, useState } from 'react'
import {
  adminGetChildren, adminGetSessions, adminGetCoinLog,
  adminCancelSession, adminDeleteChild, adminAdjustCoins, adminAdjustPocketMoney,
  adminCreateChild, adminUpdateChild, adminGetMockStatus, adminGetPocketMoneyLog,
  adminGetDevices, adminCreateDevice, adminUpdateDevice, adminDeleteDevice, adminExportDevices, adminImportDevices, adminChangePin
} from '../../api.js'
import ChildForm from './ChildForm.jsx'
import DeviceForm from './DeviceForm.jsx'

const TABS = ['Kinder', 'Sessions', 'Münz-Log', 'Taschengeld-Log', 'Geräte']

const DEVICE_TYPE_LABEL = { tv: '📺 TV', homepod: '🔊 HomePod', switch: '🎮 Switch', nintendo: '🎮 Nintendo Switch' }
const CONTROL_TYPE_LABEL = { fritzbox: '🌐 Fritz!Box', mikrotik: '⚙️ MikroTik', nintendo: 'Nintendo', schedule_only: 'Nur Zeitplan', none: '–' }

function MockStatusBar({ token }) {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    adminGetMockStatus(token).then(setStatus).catch(() => setStatus(null))
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
  const [pocketMoneyLog, setPocketMoneyLog] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [editChild, setEditChild] = useState(null) // null | 'new' | child object
  const [coinLogChild, setCoinLogChild] = useState(null)
  const [devices, setDevices] = useState([])
  const [editDevice, setEditDevice] = useState(null) // null | 'new' | device object
  const importFileRef = useRef(null)

  const handleError = (e) => {
    if (e.status === 401) { onLogout(); return }
    setError(e.message)
  }

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
      } else if (tab === 'Taschengeld-Log') {
        setPocketMoneyLog(await adminGetPocketMoneyLog(coinLogChild?.id || null, token))
      } else if (tab === 'Geräte') {
        setDevices(await adminGetDevices(token))
      }
    } catch (e) {
      handleError(e)
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
      if (e.status === 401) { onLogout(); return }
      alert(e.message)
    }
  }

  const handleDeleteChild = async (id, name) => {
    if (!confirm(`${name} wirklich löschen?`)) return
    try {
      await adminDeleteChild(id, token)
      setChildren((c) => c.filter((x) => x.id !== id))
    } catch (e) {
      if (e.status === 401) { onLogout(); return }
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
      if (e.status === 401) { onLogout(); return }
      alert(e.message)
    }
  }

  const handlePocketMoneyPayout = async (child) => {
    const raw = prompt(`Auszahlung für ${child.name} in € (z. B. 5 oder 2.50):`)
    if (raw === null) return

    const amount = Number(raw.replace(',', '.'))
    if (!Number.isFinite(amount) || amount <= 0) {
      alert('Bitte einen Betrag > 0 eingeben.')
      return
    }

    const cents = Math.round(amount * 100)

    try {
      await adminAdjustPocketMoney(child.id, -cents, 'cash_payout', 'Bar ausgezahlt', token)
      setChildren((c) =>
        c.map((x) =>
          x.id === child.id
            ? { ...x, pocket_money_cents: Math.max(0, x.pocket_money_cents - cents) }
            : x
        )
      )
    } catch (e) {
      if (e.status === 401) { onLogout(); return }
      alert(e.message)
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-900 text-white">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 bg-gray-800 border-b border-gray-700">
        <h1 className="text-xl font-black">⚙️ Eltern-Bereich</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              const currentPin = prompt('Aktuelle Admin-PIN eingeben:')
              if (!currentPin) return
              const newPin = prompt('Neue Admin-PIN eingeben (mind. 4 Zeichen):')
              if (!newPin) return
              try {
                await adminChangePin(currentPin, newPin, token)
                alert('Admin-PIN gespeichert.')
              } catch (e) {
                if (e.status === 401) { onLogout(); return }
                alert(e.message)
              }
            }}
            className="text-gray-300 hover:text-white text-sm font-bold px-3 py-2"
          >
            PIN ändern
          </button>
          <button onClick={onLogout} className="text-gray-400 hover:text-white text-lg font-bold px-4 py-2">
            Abmelden
          </button>
        </div>
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
                  Mo–Fr: {child.allowed_periods?.map((p) => `${p.von}–${p.bis}`).join(', ')} Uhr
                  {' · '}
                  WE: {child.weekend_periods?.map((p) => `${p.von}–${p.bis}`).join(', ')} Uhr
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

                <div className="flex items-center justify-between bg-gray-700/40 rounded-xl px-3 py-2">
                  <div>
                    <p className="text-sm font-bold">💶 Taschengeld: {(child.pocket_money_cents / 100).toFixed(2)} €</p>
                    <p className="text-xs text-gray-400">Wöchentlich +{(child.pocket_money_weekly_cents / 100).toFixed(2)} € (samstags)</p>
                  </div>
                  <button
                    onClick={() => handlePocketMoneyPayout(child)}
                    className="text-sm font-bold text-yellow-300 hover:text-yellow-200"
                  >
                    Auszahlung erfassen
                  </button>
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

        {/* --- Taschengeld-Log --- */}
        {!loading && tab === 'Taschengeld-Log' && (
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
            {pocketMoneyLog.length === 0 && (
              <p className="text-gray-500 text-center py-8">Kein Verlauf</p>
            )}
            {pocketMoneyLog.map((entry) => (
              <div key={entry.id} className="bg-gray-800 rounded-xl p-3 flex justify-between items-center">
                <div>
                  <p className="font-bold text-sm">{entry.child_name}</p>
                  <p className="text-gray-400 text-xs">
                    {entry.reason === 'weekly_refill' ? 'Wöchentlich aufgeladen' :
                     entry.reason === 'cash_payout' ? 'Bar ausgezahlt' : 'Anpassung'}
                  </p>
                  <p className="text-gray-500 text-xs">{new Date(entry.created_at).toLocaleString('de-DE')}</p>
                </div>
                <span className={`text-xl font-black ${entry.delta_cents > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {entry.delta_cents > 0 ? '+' : ''}{(entry.delta_cents / 100).toFixed(2)} €
                </span>
              </div>
            ))}
          </div>
        )}

        {/* --- Geräte --- */}
        {!loading && tab === 'Geräte' && (
          <div className="flex flex-col gap-3">
            <button
              onClick={() => setEditDevice('new')}
              className="w-full py-3 bg-yellow-400 hover:bg-yellow-300 text-gray-900 font-extrabold rounded-2xl active:scale-95"
            >
              + Gerät hinzufügen
            </button>
            <button
              onClick={async () => {
                try {
                  const payload = await adminExportDevices(token)
                  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `muenzbox-devices-${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.json`
                  a.click()
                  URL.revokeObjectURL(url)
                } catch (e) {
                  if (e.status === 401) { onLogout(); return }
                  alert(e.message)
                }
              }}
              className="w-full py-2 bg-blue-700 hover:bg-blue-600 text-white font-bold rounded-2xl active:scale-95"
            >
              ⬇ Geräte exportieren
            </button>
            <button
              onClick={() => importFileRef.current?.click()}
              className="w-full py-2 bg-indigo-700 hover:bg-indigo-600 text-white font-bold rounded-2xl active:scale-95"
            >
              ⬆ Geräte importieren
            </button>
            <input
              ref={importFileRef}
              type="file"
              accept="application/json"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0]
                e.target.value = ''
                if (!file) return
                try {
                  const text = await file.text()
                  const json = JSON.parse(text)
                  const devices = Array.isArray(json) ? json : (json.devices ?? [])
                  if (!Array.isArray(devices) || devices.length === 0) throw new Error('Keine Geräte im JSON gefunden')
                  const replaceExisting = confirm('Vorhandene Geräte ersetzen? OK = ersetzen, Abbrechen = hinzufügen')
                  await adminImportDevices({ devices, replace_existing: replaceExisting }, token)
                  await loadData()
                  alert('Geräte importiert')
                } catch (err) {
                  const msg = err?.message || 'Import fehlgeschlagen'
                  alert(msg)
                }
              }}
            />
            <button onClick={loadData} className="text-gray-400 hover:text-white text-sm font-bold text-right mb-2">
              ↻ Aktualisieren
            </button>
            {devices.length === 0 && (
              <p className="text-gray-500 text-center py-8">Keine Geräte</p>
            )}
            {devices.map((d) => (
              <div key={d.id} className="bg-gray-800 rounded-2xl p-4 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="font-extrabold text-base">
                    {DEVICE_TYPE_LABEL[d.device_type] ?? d.device_type} {d.name}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                      d.is_active ? 'bg-green-700 text-green-200' : 'bg-gray-700 text-gray-400'
                    }`}>
                      {d.is_active ? 'Aktiv' : 'Inaktiv'}
                    </span>
                    <button
                      onClick={() => setEditDevice(d)}
                      className="text-blue-400 hover:text-blue-300 text-sm font-bold"
                    >
                      Bearbeiten
                    </button>
                    <button
                      onClick={async () => {
                        if (!confirm(`"${d.name}" wirklich löschen?`)) return
                        try {
                          await adminDeleteDevice(d.id, token)
                          setDevices((ds) => ds.filter((x) => x.id !== d.id))
                        } catch (e) {
                          if (e.status === 401) { onLogout(); return }
                          alert(e.message)
                        }
                      }}
                      className="text-red-400 hover:text-red-300 text-sm font-bold"
                    >
                      Löschen
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-400">
                  <span className="text-gray-500">Netzwerkname</span>
                  <span className="font-mono text-yellow-300">{d.identifier ?? '–'}</span>
                  <span className="text-gray-500">Steuerung</span>
                  <span className="font-semibold text-gray-200">{CONTROL_TYPE_LABEL[d.control_type] ?? d.control_type ?? '–'}</span>
                  <span className="text-gray-500">Münztyp</span>
                  <span className="font-semibold text-gray-200">{DEVICE_TYPE_LABEL[d.device_type] ?? d.device_type}</span>
                </div>
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

      {/* Device form modal */}
      {editDevice && (
        <DeviceForm
          device={editDevice === 'new' ? null : editDevice}
          onSave={async (data) => {
            try {
              if (editDevice === 'new') {
                await adminCreateDevice(data, token)
              } else {
                await adminUpdateDevice(editDevice.id, data, token)
              }
              await loadData()
              setEditDevice(null)
            } catch (e) {
              alert(e.message)
            }
          }}
          onClose={() => setEditDevice(null)}
        />
      )}
    </div>
  )
}
