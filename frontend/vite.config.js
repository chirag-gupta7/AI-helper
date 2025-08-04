import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Open the browser automatically on `npm run dev`
    open: true,
    // Listen on this port for the frontend
    port: 3000,
    // Proxy all backend API calls to the Flask server
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false,
      },
      // Proxy all Socket.IO connections for real-time updates
      '/socket.io': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false,
        ws: true,
      }
    }
  },
  build: {
    // Output directory for production build
    outDir: 'dist',
    sourcemap: true
  }
})
