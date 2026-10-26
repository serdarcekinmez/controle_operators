import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// En développement (npm run dev), les appels /api sont transmis au serveur
// Python lancé à côté (python server.py --no-browser).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8600' },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
