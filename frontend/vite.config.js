import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import legacy from '@vitejs/plugin-legacy'

/**
 * Vite plugin that injects a safety-net loader for Safari 9 (iOS 9.3.5).
 *
 * The @vitejs/plugin-legacy emits a <script nomodule> Safari-10 fix that
 * uses the "onbeforeload" event to suppress nomodule scripts in browsers
 * that already loaded the ES-module bundle.  In Safari 9 the "beforeload"
 * event can fire for the dummy <script type="module"> before WebKit
 * realises the type is unsupported, which sets the internal flag and
 * blocks the legitimate legacy polyfill / entry scripts.
 *
 * This plugin appends a plain <script> (no nomodule, no type=module) that
 * runs after all other body scripts.  It checks whether SystemJS was
 * loaded; if not it creates <script> elements to load the polyfills and
 * then the legacy entry – completely bypassing the nomodule mechanism.
 */
function safari9LegacyFallback() {
  return {
    name: 'safari9-legacy-fallback',
    enforce: 'post',
    transformIndexHtml(html) {
      const polyfillMatch = html.match(/id="vite-legacy-polyfill"\s+src="([^"]+)"/)
      const entryMatch = html.match(/id="vite-legacy-entry"\s+data-src="([^"]+)"/)
      if (!polyfillMatch || !entryMatch) return html

      const polyfillSrc = polyfillMatch[1]
      const entrySrc = entryMatch[1]

      const fallbackScript = [
        '<script>',
        '!function(){',
        '  if("noModule" in document.createElement("script")) return;',
        '  if(typeof System!=="undefined") return;',
        '  var s=document.createElement("script");',
        '  s.src="' + polyfillSrc + '";',
        '  s.onload=function(){System.import("' + entrySrc + '")};',
        '  document.body.appendChild(s)',
        '}();',
        '</script>',
      ].join('')

      return html.replace('</body>', fallbackScript + '\n</body>')
    },
  }
}

export default defineConfig({
  plugins: [
    react(),
    legacy({
      targets: ['ios >= 9', 'safari >= 9'],
      additionalLegacyPolyfills: [
        'regenerator-runtime/runtime',
        'whatwg-fetch',
      ],
    }),
    safari9LegacyFallback(),
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://localhost:8420',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setupTests.js',
    globals: true,
  },
})
