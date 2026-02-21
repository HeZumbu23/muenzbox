import { useEffect, useState } from 'react'
import { getChildren } from '../api.js'

const AVATARS = ['🦁', '🐻', '🐼', '🦊', '🐨', '🐯', '🦄', '🐸', '🐧', '🦋']

export default function ChildSelect({ onSelect }) {
  const [children, setChildren] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    getChildren()
      .then(setChildren)
      .catch(() => setError('Verbindung fehlgeschlagen'))
  }, [])

  return (
    <div className="flex flex-col items-center justify-center h-full bg-gradient-to-b from-blue-500 to-purple-600 p-6">
      <h1 className="text-white text-5xl font-black mb-2 drop-shadow-lg">Münzbox 🪙</h1>
      <p className="text-white/80 text-xl mb-10 font-bold">Wer bist du?</p>

      {error && (
        <p className="text-red-300 text-lg mb-4 font-bold">{error}</p>
      )}

      <div className="grid grid-cols-2 gap-5 w-full max-w-lg">
        {children.map((child, i) => (
          <button
            key={child.id}
            onClick={() => onSelect(child)}
            className="bg-white/20 hover:bg-white/30 active:scale-95 transition-all duration-150
                       rounded-3xl p-6 flex flex-col items-center gap-3 shadow-xl border-2 border-white/20"
          >
            <span className="text-7xl">{AVATARS[i % AVATARS.length]}</span>
            <span className="text-white text-2xl font-extrabold">{child.name}</span>
          </button>
        ))}
      </div>

      <button
        onClick={() => (window.location.href = '/eltern')}
        className="absolute bottom-6 right-6 text-white/40 hover:text-white/70 text-sm font-bold transition-colors"
      >
        Eltern ⚙️
      </button>
    </div>
  )
}
