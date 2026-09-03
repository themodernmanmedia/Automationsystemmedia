/**
 * Content lifecycle state machine.
 *
 * The brief specifies an explicit lifecycle, so it is enforced as data rather
 * than left to whichever worker happens to update a row. An illegal transition
 * throws — which is what makes "a piece cannot reach PUBLISHED without passing
 * QA" a structural guarantee instead of a convention that erodes.
 */
import { ValidationError } from '@mmos/core';

export const CONTENT_STATUSES = [
  'DISCOVERED',
  'RESEARCHING',
  'RESEARCHED',
  'WRITING',
  'DESIGNING',
  'QA',
  'APPROVED',
  'SCHEDULED',
  'PUBLISHING',
  'PUBLISHED',
  'ANALYZING',
  'LEARNED',
  'FLAGGED',
  'FAILED',
  'ARCHIVED',
] as const;

export type ContentStatus = (typeof CONTENT_STATUSES)[number];

/**
 * Allowed transitions. Two rules are deliberate:
 *  - Every pre-publish state can move to FLAGGED. That is the exception queue,
 *    and it must always be reachable or autonomous mode has no escape hatch.
 *  - PUBLISHED cannot go backwards. Once it is live, the record is history.
 */
const TRANSITIONS: Record<ContentStatus, readonly ContentStatus[]> = {
  DISCOVERED: ['RESEARCHING', 'FLAGGED', 'ARCHIVED'],
  RESEARCHING: ['RESEARCHED', 'FAILED', 'FLAGGED', 'ARCHIVED'],
  RESEARCHED: ['WRITING', 'FLAGGED', 'ARCHIVED'],
  WRITING: ['DESIGNING', 'QA', 'FAILED', 'FLAGGED', 'ARCHIVED'],
  DESIGNING: ['QA', 'FAILED', 'FLAGGED', 'ARCHIVED'],
  // QA can send work back to DESIGNING — a failed brand check is fixable.
  QA: ['APPROVED', 'DESIGNING', 'WRITING', 'FLAGGED', 'FAILED', 'ARCHIVED'],
  APPROVED: ['SCHEDULED', 'PUBLISHING', 'FLAGGED', 'ARCHIVED'],
  SCHEDULED: ['PUBLISHING', 'APPROVED', 'FLAGGED', 'ARCHIVED'],
  PUBLISHING: ['PUBLISHED', 'FAILED', 'FLAGGED'],
  PUBLISHED: ['ANALYZING', 'ARCHIVED'],
  ANALYZING: ['LEARNED', 'ARCHIVED'],
  LEARNED: ['ARCHIVED'],
  // A flagged piece can rejoin the pipeline once a human resolves it.
  FLAGGED: ['WRITING', 'DESIGNING', 'QA', 'APPROVED', 'ARCHIVED'],
  FAILED: ['WRITING', 'DESIGNING', 'QA', 'ARCHIVED'],
  ARCHIVED: [],
};

export function canTransition(from: ContentStatus, to: ContentStatus): boolean {
  return TRANSITIONS[from].includes(to);
}

export function assertTransition(from: ContentStatus, to: ContentStatus): void {
  if (!canTransition(from, to)) {
    throw new ValidationError(
      `Illegal content lifecycle transition: ${from} -> ${to}. Allowed from ${from}: ${TRANSITIONS[from].join(', ') || '(none — terminal state)'}`,
      { from, to },
    );
  }
}

export function allowedTransitions(from: ContentStatus): readonly ContentStatus[] {
  return TRANSITIONS[from];
}

/** States that must never be published from. Checked immediately before publish. */
export const NON_PUBLISHABLE: readonly ContentStatus[] = [
  'DISCOVERED', 'RESEARCHING', 'RESEARCHED', 'WRITING', 'DESIGNING',
  'QA', 'FLAGGED', 'FAILED', 'ARCHIVED',
];

export function isPublishable(status: ContentStatus): boolean {
  return !NON_PUBLISHABLE.includes(status);
}

/** Terminal states — no further automated work is scheduled. */
export function isTerminal(status: ContentStatus): boolean {
  return TRANSITIONS[status].length === 0;
}
