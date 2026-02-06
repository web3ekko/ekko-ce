import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react({
      // Disable fast refresh to avoid potential issues
      fastRefresh: false,
    })
  ],
  server: {
    host: '0.0.0.0', // Listen on all interfaces
    port: 3000,
    strictPort: true,
    hmr: {
      overlay: false
    }
  },
  build: {
    target: 'es2015',
    minify: false
  }
})
