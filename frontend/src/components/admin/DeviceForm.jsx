import { useState } from 'react'

const DEVICE_TYPE_OPTIONS = [
  { value: 'tv', label: '📺 Fernseher' },
]

export default function DeviceForm({ device, onSave, onClose }) {
  const isNew = !device
  const [form, setForm] = useState({
    name: device?.identifier ?? device?.name ?? '',
    device_type: device?.device_type ?? 'tv',
  })
  const [saving, setSaving] = useState(false)

  const update = (key, val) => setForm((f) => ({ ...f, [key]: val }))

  const handleSave = async () => {
    if (!form.name.trim()) { alert('Fritz!Box Netzwerkname erforderlich'); return }
    setSaving(true)
    try {
      await onSave(form)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="absolute inset-0 bg-black/80 flex items-end justify-center z-50">
      <div className="bg-gray-900 w-full max-w-lg rounded-t-3xl p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-white text-xl font-black">
            {isNew ? 'Gerät hinzufügen' : 'Gerät bearbeiten'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-2xl font-bold">×</button>
        </div>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-gray-400 text-xs font-bold uppercase tracking-wider">
              Fritz!Box Netzwerkname
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => update('name', e.target.value)}
              placeholder="z. B. samsung-tv"
              className="bg-gray-700 text-white rounded-xl px-3 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-yellow-400"
            />
            <p className="text-gray-500 text-xs mt-1">
              Hostname/Netzwerkname des Geräts in der Fritz!Box
            </p>
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-gray-400 text-xs font-bold uppercase tracking-wider">
              Münztyp
            </label>
            <select
              value={form.device_type}
              onChange={(e) => update('device_type', e.target.value)}
              className="bg-gray-700 text-white rounded-xl px-3 py-2 text-sm font-bold focus:outline-none focus:ring-2 focus:ring-yellow-400"
            >
              {DEVICE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
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
