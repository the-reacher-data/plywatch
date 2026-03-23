import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    proxy: {
      '/api': {
        target: 'http://plywatch:8080',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://plywatch:8080',
        changeOrigin: true,
      },
    },
  },
});
