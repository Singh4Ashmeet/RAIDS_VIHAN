import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 1100,
    rolldownOptions: {
      output: {
        codeSplitting: true,
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return
          }

          if (id.includes('react') || id.includes('scheduler')) {
            return 'vendor-react'
          }

          if (id.includes('recharts')) {
            return 'vendor-charts'
          }

          if (id.includes('framer-motion')) {
            return 'vendor-motion'
          }

          if (
            id.includes('maplibre-gl') ||
            id.includes('@maplibre') ||
            id.includes('@mapbox') ||
            id.includes('geojson-vt') ||
            id.includes('supercluster') ||
            id.includes('quickselect') ||
            id.includes('kdbush')
          ) {
            return 'vendor-map'
          }

          if (id.includes('react-router-dom')) {
            return 'vendor-router'
          }

          if (id.includes('axios') || id.includes('zustand')) {
            return 'vendor-state'
          }

          if (id.includes('lucide-react')) {
            return 'vendor-icons'
          }

          return 'vendor'
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
