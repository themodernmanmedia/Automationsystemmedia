import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    globalSetup: [],
    setupFiles: ['./test/setup.ts'],
    include: ['packages/**/*.test.ts', 'apps/**/*.test.ts'],
    exclude: ['**/node_modules/**', '**/dist/**', '**/.next/**'],
    testTimeout: 30_000,
    coverage: { provider: 'v8', reporter: ['text', 'html'] },
  },
});
