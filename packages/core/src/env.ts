/**
 * Side-effect module: loads the root `.env` the moment it is imported.
 *
 * It exists as a separate entry point because ESM evaluates imports before any
 * statement in the importing module runs. `@mmos/db` constructs its
 * PrismaClient at import time, and that reads `DATABASE_URL` immediately — so
 * calling a load function inside `main()` would already be too late. Importing
 * this first, above every other import, is what makes the ordering correct.
 *
 *   import '@mmos/core/env';   // must be the first import
 *   import { prisma } from '@mmos/db';
 */
import { loadDotEnv } from './config.js';

loadDotEnv();
