import { useState } from 'react'

function Field({ label, value, type = 'text', min, max, onChange }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-gray-400 text-xs font-bold uppercase tracking-wider">{label}</label>
      <input
        type={type}
        value={value}
        min={min}
        max={max}
        onChange={onChange}
        className="bg-gray-700 text-white rounded-xl px-3 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-yellow-400"
      />
    </div>
  )
}

export default function ChildForm({ child, onSave, onClose }) {
  const isNew = !child
  const [form, setForm] = useState({
    name: child?.name ?? '',
    pin: '',
    switch_coins: child?.switch_coins ?? 0,
    switch_coins_weekly: child?.switch_coins_weekly ?? 2,
    switch_coins_max: child?.switch_coins_max ?? 10,
    tv_coins: child?.tv_coins ?? 0,
    tv_coins_weekly: child?.tv_coins_weekly ?? 2,
    tv_coins_max: child?.tv_coins_max ?? 10,
    allowed_from: child?.allowed_from ?? '08:00',
    allowed_until: child?.allowed_until ?? '20:00',
    weekend_from: child?.weekend_from ?? '08:00',
    weekend_until: child?.weekend_until ?? '20:00',
  })
  const [saving, setSaving] = useState(false)

  const update = (key, val) => setForm((f) => ({ ...f, [key]: val }))

  const handleSave = async () => {
    if (!form.name.trim()) { alert('Name erforderlich'); return }
    if (isNew && form.pin.length < 4) { alert('PIN: mindestens 4 Ziffern'); return }
    setSaving(true)
    try {
      const data = { ...form }
      if (!data.pin) delete data.pin
      await onSave(data)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="absolute inset-0 bg-black/80 flex items-end justify-center z-50">
      <div className="bg-gray-900 w-full max-w-lg rounded-t-3xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-white text-xl font-black">
            {isNew ? 'Kind hinzufügen' : `${child.name} bearbeiten`}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-2xl font-bold">×</button>
        </div>

        <div className="flex flex-col gap-4">
          <Field
            label="Name"
            value={form.name}
            onChange={(e) => update('name', e.target.value)}
          />
          <Field
            label={isNew ? 'PIN (min. 4 Ziffern)' : 'Neue PIN (leer lassen = unverändert)'}
            value={form.pin}
            type="number"
            onChange={(e) => update('pin', e.target.value)}
          />

          <div className="border-t border-gray-700 pt-4">
            <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-3">🎮 Nintendo Switch</p>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Aktuell" value={form.switch_coins} type="number" min={0} onChange={(e) => update('switch_coins', parseInt(e.target.value) || 0)} />
              <Field label="+/Woche" value={form.switch_coins_weekly} type="number" min={0} onChange={(e) => update('switch_coins_weekly', parseInt(e.target.value) || 0)} />
              <Field label="Maximum" value={form.switch_coins_max} type="number" min={1} onChange={(e) => update('switch_coins_max', parseInt(e.target.value) || 0)} />
            </div>
          </div>

          <div className="border-t border-gray-700 pt-4">
            <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-3">📺 Fernseher</p>
            <div className="grid grid-cols-3 gap-3">
              <Field label="Aktuell" value={form.tv_coins} type="number" min={0} onChange={(e) => update('tv_coins', parseInt(e.target.value) || 0)} />
              <Field label="+/Woche" value={form.tv_coins_weekly} type="number" min={0} onChange={(e) => update('tv_coins_weekly', parseInt(e.target.value) || 0)} />
              <Field label="Maximum" value={form.tv_coins_max} type="number" min={1} onChange={(e) => update('tv_coins_max', parseInt(e.target.value) || 0)} />
            </div>
          </div>

          <div className="border-t border-gray-700 pt-4">
            <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-3">⏰ Erlaubte Zeiten</p>
            <p className="text-gray-500 text-xs mb-2">Mo – Fr</p>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <Field label="Von" value={form.allowed_from} type="time" onChange={(e) => update('allowed_from', e.target.value)} />
              <Field label="Bis" value={form.allowed_until} type="time" onChange={(e) => update('allowed_until', e.target.value)} />
            </div>
            <p className="text-gray-500 text-xs mb-2">Sa, So & Feiertage</p>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Von" value={form.weekend_from} type="time" onChange={(e) => update('weekend_from', e.target.value)} />
              <Field label="Bis" value={form.weekend_until} type="time" onChange={(e) => update('weekend_until', e.target.value)} />
            </div>
          </div>

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
