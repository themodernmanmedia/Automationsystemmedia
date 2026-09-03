import { describe, expect, it } from 'vitest';
import { assertTransition, canTransition, isPublishable, isTerminal, CONTENT_STATUSES } from './lifecycle.js';

describe('content lifecycle', () => {
  it('permits the normal happy path end to end', () => {
    const path = [
      'DISCOVERED', 'RESEARCHING', 'RESEARCHED', 'WRITING', 'DESIGNING',
      'QA', 'APPROVED', 'SCHEDULED', 'PUBLISHING', 'PUBLISHED', 'ANALYZING', 'LEARNED',
    ] as const;
    for (let i = 0; i < path.length - 1; i++) {
      expect(canTransition(path[i]!, path[i + 1]!)).toBe(true);
    }
  });

  it('refuses to skip QA on the way to publishing', () => {
    expect(canTransition('DESIGNING', 'PUBLISHING')).toBe(false);
    expect(() => assertTransition('DESIGNING', 'PUBLISHED')).toThrow(/Illegal content lifecycle transition/);
  });

  it('never allows a published piece to move backwards', () => {
    for (const s of ['WRITING', 'QA', 'SCHEDULED', 'PUBLISHING'] as const) {
      expect(canTransition('PUBLISHED', s)).toBe(false);
    }
  });

  it('keeps the exception queue reachable from every pre-publish state', () => {
    const prePublish = ['DISCOVERED', 'RESEARCHING', 'RESEARCHED', 'WRITING', 'DESIGNING', 'QA', 'APPROVED', 'SCHEDULED'] as const;
    for (const s of prePublish) expect(canTransition(s, 'FLAGGED')).toBe(true);
  });

  it('lets a human return a flagged piece to the pipeline', () => {
    expect(canTransition('FLAGGED', 'APPROVED')).toBe(true);
    expect(canTransition('FLAGGED', 'DESIGNING')).toBe(true);
  });

  it('treats ARCHIVED as terminal and reachable from every settled state', () => {
    expect(isTerminal('ARCHIVED')).toBe(true);
    for (const s of CONTENT_STATUSES) {
      // PUBLISHING is excluded on purpose: a piece mid-flight to a platform
      // must resolve to PUBLISHED or FAILED first. Archiving it while the
      // publish call is outstanding would desync us from the platform.
      if (s === 'ARCHIVED' || s === 'PUBLISHING') continue;
      expect(canTransition(s, 'ARCHIVED')).toBe(true);
    }
    expect(canTransition('PUBLISHING', 'ARCHIVED')).toBe(false);
  });

  it('blocks publishing from any unfinished state', () => {
    expect(isPublishable('QA')).toBe(false);
    expect(isPublishable('FLAGGED')).toBe(false);
    expect(isPublishable('APPROVED')).toBe(true);
    expect(isPublishable('SCHEDULED')).toBe(true);
  });
});
