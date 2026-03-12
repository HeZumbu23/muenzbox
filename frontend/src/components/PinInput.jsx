import { useEffect, useState } from 'react'
import { verifyPin } from '../api.js'

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '⌫', '0', '✓']

export default function PinInput({ child, onSuccess, onBack }) {
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)


  useEffect(() => {
    const onKeyDown = (e) => {
      if (loading) return
      if (/^[0-9]$/.test(e.key)) {
        e.preventDefault()
        handleKey(e.key)
        return
      }
      if (e.key === 'Backspace') {
        e.preventDefault()
        handleKey('⌫')
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        handleKey('✓')
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [loading, pin])

  const handleKey = async (key) => {
    if (loading) return
    setError('')

    if (key === '⌫') {
      setPin((p) => p.slice(0, -1))
      return
    }

    if (key === '✓') {
      if (pin.length < 4) {
        setError('Bitte 4 Ziffern eingeben')
        return
      }
      setLoading(true)
      try {
        const res = await verifyPin(child.id, pin)
        onSuccess(res.token, res.child_id, res.name, res.icon)
      } catch {
        setError('Falsche PIN!')
        setPin('')
      } finally {
        setLoading(false)
      }
      return
    }

    if (pin.length < 8) {
      setPin((p) => p + key)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center h-full bg-gradient-to-b from-blue-500 to-purple-600 p-6">
      <button
        onClick={onBack}
        className="absolute top-6 left-6 text-white/60 hover:text-white text-3xl font-bold transition-colors"
      >
        ←
      </button>

      <p className="text-white/70 text-xl font-bold mb-1">Hallo</p>
      <h2 className="text-white text-5xl font-black mb-8 drop-shadow">{child.name}</h2>

      {/* PIN dots */}
      <div className="flex gap-4 mb-3">
        {Array.from({ length: Math.max(4, pin.length) }).map((_, i) => (
          <div
            key={i}
            className={`w-6 h-6 rounded-full border-2 border-white/60 transition-all ${
              i < pin.length ? 'bg-yellow-400 border-yellow-400 scale-110' : 'bg-transparent'
            }`}
          />
        ))}
      </div>

      {error && (
        <p className="text-red-300 text-lg font-extrabold mb-2 animate-pulse">{error}</p>
      )}
      <div className="h-6 mb-4" />

      {/* Numpad – uses flexbox (CSS Grid not supported on Safari 9) */}
      <div className="flex flex-wrap justify-center w-full max-w-xs">
        {KEYS.map((key) => (
          <div key={key} className="w-1/3 p-2">
            <button
              onClick={() => handleKey(key)}
              disabled={loading}
              className={`w-full h-20 text-3xl font-extrabold rounded-2xl shadow-lg transition-all duration-100 active:scale-90
                ${key === '✓'
                  ? 'bg-green-400 hover:bg-green-300 text-white'
                  : 'bg-white/20 hover:bg-white/30 text-white'
                }
                ${loading ? 'opacity-50' : ''}
              `}
            >
              {loading && key === '✓' ? '...' : key}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
