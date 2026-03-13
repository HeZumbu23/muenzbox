import { useEffect, useState } from 'react'
import { getChildren } from '../api.js'
import Icon from './Icon.jsx'

// Only emojis available on iOS 9.3.5 (Unicode 8.0 / Emoji 1.0)
const AVATARS = ['🐻', '🐼', '🐨', '🐯', '🐸', '🐧', '🐵', '🐶', '🐱', '🐰']

export default function ChildSelect({ onSelect }) {
  const [children, setChildren] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getChildren()
      .then(setChildren)
      .catch(() => setError('Verbindung fehlgeschlagen'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="flex flex-col items-center justify-center h-full bg-gradient-to-b from-blue-500 to-purple-600 p-6">
      <h1 className="text-white text-5xl font-black mb-2 drop-shadow-lg">Münzbox</h1>
      <p className="text-white/80 text-xl mb-6 font-bold">Wer bist du?</p>

      {error && (
        <p className="text-red-300 text-lg mb-4 font-bold">{error}</p>
      )}

      {!loading && !error && children.length === 0 && (
        <p className="text-white/60 text-lg font-bold text-center">
          Noch keine Kinder angelegt.<br />
          <span className="text-white/40 text-base">Bitte im Eltern-Bereich hinzufügen.</span>
        </p>
      )}

      {/* Flexbox statt CSS Grid (Safari 9 kompatibel) */}
      <div className="flex flex-wrap justify-center w-full max-w-2xl">
        {children.map((child, i) => (
          <div key={child.id} className="w-1/2 p-3">
            <button
              onClick={() => onSelect(child)}
              className="w-full bg-white/20 hover:bg-white/30 active:scale-95 transition-all duration-150
                         rounded-3xl p-6 flex flex-col items-center gap-3 shadow-xl border-2 border-white/20"
            >
              <Icon emoji={child.icon || AVATARS[i % AVATARS.length]} size="4.5rem" />
              <span className="text-white text-2xl font-extrabold">{child.name}</span>
              <div className="flex gap-4 text-white/90 text-lg font-bold">
                <span><Icon emoji="🎮" size="1.1em" /> {child.switch_coins}</span>
                <span><Icon emoji="📺" size="1.1em" /> {child.tv_coins}</span>
              </div>
            </button>
          </div>
        ))}
      </div>

      <button
        onClick={() => (window.location.href = '/eltern')}
        className="absolute right-6 bottom-14 z-20 sm:bottom-6 text-white/70 hover:text-white text-sm font-bold transition-colors bg-white/10 hover:bg-white/20 px-3 py-1 rounded-full"
      >
        Eltern <Icon emoji="⚙️" size="0.9em" />
      </button>
    </div>
  )
}
