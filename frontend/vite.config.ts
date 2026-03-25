import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';
/// <reference types="vitest" />

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react(), tailwindcss()],
    define: {
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test-setup.ts'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html'],
        include: [
          'src/components/**/*.{ts,tsx}',
          'src/hooks/**/*.{ts,tsx}',
          'src/pages/**/*.{ts,tsx}',
          'src/api/**/*.{ts,tsx}',
        ],
        exclude: [
          'src/main.tsx',
          'src/index.tsx',
          '**/*.d.ts',
          '**/interfaces.ts',
          '**/types.ts',
          '**/*.test.{ts,tsx}',
          'src/test-setup.ts',
        ],
        threshold: {
          lines: 70,
          functions: 70,
          branches: 70,
          statements: 70,
        },
      },
    },
  };
});
