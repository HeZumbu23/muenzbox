import { useState } from 'react'
import { adminVerify } from '../../api.js'

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '⌫', '0', '✓']

export default function AdminLogin({ onSuccess }) {
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleKey = async (key) => {
    if (loading) return
    setError('')

    if (key === '⌫') {
      setPin((p) => p.slice(0, -1))
      return
    }

    if (key === '✓') {
      if (pin.length < 4) {
        setError('Bitte PIN eingeben')
        return
      }
      setLoading(true)
      try {
        const res = await adminVerify(pin)
        onSuccess(res.token)
      } catch {
        setError('Falsche Admin-PIN!')
        setPin('')
      } finally {
        setLoading(false)
      }
      return
    }

    if (pin.length < 8) setPin((p) => p + key)
  }

  return (
    <div className="flex flex-col items-center justify-center h-full bg-gradient-to-b from-gray-700 to-gray-900 p-6">
      <a href="/" className="absolute top-6 left-6 text-white/40 hover:text-white/70 text-sm font-bold">
        ← Zurück
      </a>

      <h1 className="text-white text-4xl font-black mb-1">Eltern-Bereich</h1>
      <p className="text-white/60 text-lg font-bold mb-8">Admin-PIN eingeben</p>

      <div className="flex gap-4 mb-3">
        {Array.from({ length: Math.max(4, pin.length) }).map((_, i) => (
          <div
            key={i}
            className={`w-5 h-5 rounded-full border-2 border-white/40 transition-all ${
              i < pin.length ? 'bg-yellow-400 border-yellow-400 scale-110' : 'bg-transparent'
            }`}
          />
        ))}
      </div>

      {error && <p className="text-red-400 font-extrabold mb-2 animate-pulse">{error}</p>}
      <div className="h-4 mb-4" />

      <div className="grid grid-cols-3 gap-4 w-full max-w-xs">
        {KEYS.map((key) => (
          <button
            key={key}
            onClick={() => handleKey(key)}
            disabled={loading}
            className={`h-16 text-2xl font-extrabold rounded-2xl shadow transition-all active:scale-90
              ${key === '✓' ? 'bg-green-500 hover:bg-green-400 text-white' :
                key === '⌫' ? 'bg-white/10 hover:bg-white/20 text-white' :
                'bg-white/10 hover:bg-white/20 text-white'}
              ${loading ? 'opacity-50' : ''}
            `}
          >
            {loading && key === '✓' ? '...' : key}
          </button>
        ))}
      </div>
    </div>
  )
}
