import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: 'unit-node',
          environment: 'node',
          include: ['src/**/*.test.js'],
          exclude: ['src/components/**', 'src/views/**'],
        },
      },
      {
        extends: true,
        test: {
          name: 'unit-vue',
          environment: 'jsdom',
          include: [
            'src/components/**/*.test.{js,ts}',
            'src/views/**/*.test.{js,ts}',
          ],
        },
      },
    ],
  },
  server: {
    port: 3000,
    open: true,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false
      }
    }
  }
})
