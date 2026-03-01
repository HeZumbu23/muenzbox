import { useState } from 'react'

const DEVICE_TYPE_OPTIONS = [
  { value: 'tv', label: '📺 Fernseher' },
]

const CONTROL_TYPE_OPTIONS = [
  { value: 'fritzbox', label: '🌐 Fritz!Box' },
  { value: 'mikrotik', label: '⚙️ MikroTik' },
  { value: 'schedule_only', label: '🕐 Nur Zeitplan (keine Hardware)' },
  { value: 'none', label: '— Keine Steuerung' },
]

function Field({ label, hint, children }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-gray-400 text-xs font-bold uppercase tracking-wider">{label}</label>
      {children}
      {hint && <p className="text-gray-500 text-xs mt-0.5">{hint}</p>}
    </div>
  )
}

function Input({ value, onChange, placeholder, type = 'text' }) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      autoComplete="off"
      className="bg-gray-700 text-white rounded-xl px-3 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-yellow-400"
    />
  )
}

export default function DeviceForm({ device, onSave, onClose }) {
  const isNew = !device
  const [form, setForm] = useState({
    name: device?.name ?? '',
    identifier: device?.identifier ?? '',
    device_type: device?.device_type ?? 'tv',
    control_type: device?.control_type ?? 'fritzbox',
    config: device?.config ?? {},
  })
  const [saving, setSaving] = useState(false)

  const update = (key, val) => setForm((f) => ({ ...f, [key]: val }))
  const updateCfg = (key, val) => setForm((f) => ({ ...f, config: { ...f.config, [key]: val } }))
  const cfg = form.config

  const handleSave = async () => {
    if (!form.name.trim()) { alert('Anzeigename erforderlich'); return }
    if (!form.identifier.trim()) { alert('Netzwerkname des Geräts erforderlich'); return }
    setSaving(true)
    try {
      await onSave(form)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="absolute inset-0 bg-black/80 flex items-end justify-center z-50">
      <div className="bg-gray-900 w-full max-w-lg rounded-t-3xl p-6 max-h-[92vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-white text-xl font-black">
            {isNew ? 'Gerät hinzufügen' : 'Gerät bearbeiten'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-2xl font-bold">×</button>
        </div>

        <div className="flex flex-col gap-4">

          {/* Allgemein */}
          <Field label="Anzeigename">
            <Input value={form.name} onChange={(v) => update('name', v)} placeholder="z. B. Wohnzimmer TV" />
          </Field>

          <Field label="Münztyp">
            <select
              value={form.device_type}
              onChange={(e) => update('device_type', e.target.value)}
              className="bg-gray-700 text-white rounded-xl px-3 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-yellow-400"
            >
              {DEVICE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </Field>

          {/* Steuerung */}
          <div className="border-t border-gray-700 pt-4">
            <p className="text-gray-500 text-xs font-bold uppercase tracking-wider mb-3">Steuerung</p>

            <Field label="Methode">
              <select
                value={form.control_type}
                onChange={(e) => {
                  const newType = e.target.value
                  if (newType !== form.control_type) {
                    updateCfg('password', '')
                  }
                  update('control_type', newType)
                }}
                className="bg-gray-700 text-white rounded-xl px-3 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-yellow-400"
              >
                {CONTROL_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </Field>
          </div>

          {/* Fritz!Box Konfiguration */}
          {form.control_type === 'fritzbox' && (
            <div className="flex flex-col gap-3 bg-gray-800 rounded-2xl p-4">
              <p className="text-yellow-400 text-xs font-bold uppercase tracking-wider">🌐 Fritz!Box Zugangsdaten</p>

              <Field label="Adresse" hint="z. B. fritz.box oder 192.168.178.1">
                <Input value={cfg.host ?? ''} onChange={(v) => updateCfg('host', v)} placeholder="fritz.box" />
              </Field>

              <Field label="Benutzer" hint="Leer lassen wenn kein Benutzer konfiguriert">
                <Input value={cfg.user ?? ''} onChange={(v) => updateCfg('user', v)} placeholder="" />
              </Field>

              <Field label="Passwort">
                <Input value={cfg.password ?? ''} onChange={(v) => updateCfg('password', v)} placeholder="••••••••" type="password" />
              </Field>

              <Field label="Freigabe-Profil" hint="Name des Kindersicherungs-Profils für freigegebene Geräte">
                <Input value={cfg.allowed_profile ?? ''} onChange={(v) => updateCfg('allowed_profile', v)} placeholder="Standard" />
              </Field>

              <Field label="Sperr-Profil" hint="Name des Kindersicherungs-Profils für gesperrte Geräte">
                <Input value={cfg.blocked_profile ?? ''} onChange={(v) => updateCfg('blocked_profile', v)} placeholder="Gesperrt" />
              </Field>

              <Field label="Gerätename in Fritz!Box" hint="Hostname wie er in der Fritz!Box Heimnetz-Übersicht steht">
                <Input value={form.identifier} onChange={(v) => update('identifier', v)} placeholder="samsung-tv" />
              </Field>
            </div>
          )}

          {/* MikroTik Konfiguration */}
          {form.control_type === 'mikrotik' && (
            <div className="flex flex-col gap-3 bg-gray-800 rounded-2xl p-4">
              <p className="text-yellow-400 text-xs font-bold uppercase tracking-wider">⚙️ MikroTik</p>
              <p className="text-gray-400 text-xs">Zugangsdaten (Host, Benutzer, Passwort) werden aus der <code>.env</code> geladen: <code>MIKROTIK_HOST</code>, <code>MIKROTIK_USER</code>, <code>MIKROTIK_PASS</code></p>

              <Field label="Address-List Kommentar" hint="comment-Feld des Eintrags in der Firewall Address-List">
                <Input value={form.identifier} onChange={(v) => update('identifier', v)} placeholder="Fernseher" />
              </Field>
            </div>
          )}

          {/* schedule_only / none: kein weiteres Feld */}
          {(form.control_type === 'schedule_only' || form.control_type === 'none') && (
            <div className="flex flex-col gap-3 bg-gray-800 rounded-2xl p-4">
              <Field label="Gerätename" hint="Interner Name zur Identifikation">
                <Input value={form.identifier} onChange={(v) => update('identifier', v)} placeholder="mein-geraet" />
              </Field>
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              className="flex-1 py-3 bg-gray-700 hover:bg-gray-600 text-white font-bold rounded-2xl active:scale-95"
            >
              Abbrechen
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 py-3 bg-yellow-400 hover:bg-yellow-300 text-gray-900 font-extrabold rounded-2xl active:scale-95 disabled:opacity-50"
            >
              {saving ? 'Speichern…' : 'Speichern'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
