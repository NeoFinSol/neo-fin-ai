import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Consolidated API proxy configuration
      // All API calls should use /api prefix
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        // Remove /api prefix when proxying to backend
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
