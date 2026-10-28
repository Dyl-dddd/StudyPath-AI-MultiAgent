import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replaceAll('\\', '/')
          if (normalizedId.includes('/node_modules/zrender/')) return 'zrender'
          if (normalizedId.includes('/node_modules/echarts/')) return 'echarts'
        },
      },
    },
  },
})
