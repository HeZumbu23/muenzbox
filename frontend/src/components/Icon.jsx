// Icon component: renders emoji as GIF images for Safari 9.3.5 compatibility.
// GIF files are extracted from NotoColorEmoji and stored in /public/icons/.
const EMOJI_TO_GIF = {
  '🎮': 'gamepad',
  '📺': 'tv',
  '🐻': 'bear',
  '🐼': 'panda',
  '🐨': 'koala',
  '🐯': 'tiger',
  '🐸': 'frog',
  '🐧': 'penguin',
  '🐵': 'monkey',
  '🐶': 'dog',
  '🐱': 'cat',
  '🐰': 'rabbit',
  '🐙': 'octopus',
  '🐮': 'cow',
  '⚙️': 'gear',
  '\u2699': 'gear',
  '🎉': 'party',
  '🚀': 'rocket',
  '🧠': 'brain',
  '✅': 'check',
  '⚠️': 'warning',
  '\u26a0': 'warning',
  '🧪': 'flask',
  '🔒': 'lock',
  '🌐': 'globe',
  '🕐': 'clock',
  '🪙': 'coin',
}

/**
 * Renders an emoji as a GIF image for cross-browser compatibility.
 * Falls back to the raw emoji character if no GIF mapping exists.
 *
 * @param {string} emoji - The emoji character (e.g. '🎮')
 * @param {string} [size='1em'] - CSS size for width/height (e.g. '2rem', '1.5em')
 * @param {string} [className=''] - Additional CSS classes
 * @param {object} [style={}] - Additional inline styles
 */
export default function Icon({ emoji, size = '1em', className = '', style = {} }) {
  const gifName = EMOJI_TO_GIF[emoji]
  if (!gifName) {
    return <span className={className} style={style}>{emoji}</span>
  }
  return (
    <img
      src={'/icons/' + gifName + '.gif'}
      alt={emoji}
      className={className}
      style={Object.assign({ display: 'inline-block', verticalAlign: '-0.1em', height: size, width: size }, style)}
    />
  )
}
