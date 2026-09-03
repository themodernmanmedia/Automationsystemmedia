import { describe, expect, it } from 'vitest';
import { extractJson } from './json.js';

describe('extractJson', () => {
  it('parses clean JSON', () => {
    expect(extractJson('{"a":1}')).toEqual({ a: 1 });
  });

  it('recovers JSON from a markdown fence', () => {
    expect(extractJson('```json\n{"a":1}\n```')).toEqual({ a: 1 });
    expect(extractJson('```\n{"a":1}\n```')).toEqual({ a: 1 });
  });

  it('recovers JSON wrapped in prose', () => {
    expect(extractJson('Here is the result:\n{"a":1}\nHope that helps!')).toEqual({ a: 1 });
  });

  it('does not truncate on a brace inside a string', () => {
    // A caption containing a brace used to break naive extraction.
    const input = 'Result: {"caption":"Use {this} format","n":2} done';
    expect(extractJson(input)).toEqual({ caption: 'Use {this} format', n: 2 });
  });

  it('handles escaped quotes inside strings', () => {
    expect(extractJson('{"quote":"He said \\"no\\" firmly"}')).toEqual({ quote: 'He said "no" firmly' });
  });

  it('extracts a top-level array', () => {
    expect(extractJson('prefix [1,2,3] suffix')).toEqual([1, 2, 3]);
  });

  it('throws when there is no JSON at all', () => {
    expect(() => extractJson('I cannot help with that.')).toThrow(/No JSON object found/);
  });
});
