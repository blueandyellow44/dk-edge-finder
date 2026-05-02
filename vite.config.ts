import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { cloudflare } from '@cloudflare/vite-plugin'

export default defineConfig({
  root: 'frontend',
  plugins: [react(), cloudflare()],
  server: {
    proxy: {
      // In dev we run wrangler dev separately on 8787 for the Worker, then
      // hit Vite on 5173 for HMR. The proxy hands /api/* to the running
      // Worker (with the cf-access-authenticated-user-email header that
      // api/client.ts injects in dev) so the SPA sees real KV state.
      '/api': 'http://localhost:8787',
    },
  },
})
