import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    globalSetup: [],
    setupFiles: ['./test/setup.ts'],
    include: ['packages/**/*.test.ts', 'apps/**/*.test.ts'],
    exclude: ['**/node_modules/**', '**/dist/**', '**/.next/**'],
    testTimeout: 60_000,
    /**
     * Test FILES run one at a time.
     *
     * Several suites exercise real Postgres, and they cannot safely overlap:
     * the API suite requires a database with zero organizations (registration
     * is single-use by design) and truncates to get there, which would destroy
     * data another suite is mid-way through using. Isolating by schema would
     * mean migrating per file for little gain at this suite size, so files are
     * simply serialized. Tests within a file still run normally.
     */
    fileParallelism: false,
    coverage: { provider: 'v8', reporter: ['text', 'html'] },
  },
});
