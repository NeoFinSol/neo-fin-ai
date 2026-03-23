import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Secure proxy configuration for development
      // Only proxies specific API paths to backend
      '/upload': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/result': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/analyze': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '/system': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
