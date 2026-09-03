/**
 * Tolerant JSON extraction from model output.
 *
 * Models sometimes wrap JSON in prose or a markdown fence despite instructions.
 * Rather than failing an otherwise-good generation (and paying for a retry),
 * we recover the object. This never repairs malformed JSON — it only locates
 * valid JSON inside surrounding text.
 */
export function extractJson(text: string): unknown {
  const trimmed = text.trim();

  try {
    return JSON.parse(trimmed);
  } catch {
    /* fall through to recovery */
  }

  // ```json ... ``` fences
  const fenced = trimmed.match(/```(?:json)?\s*\n?([\s\S]*?)```/);
  if (fenced?.[1]) {
    try {
      return JSON.parse(fenced[1].trim());
    } catch {
      /* keep trying */
    }
  }

  // First balanced { … } or [ … ], respecting strings and escapes so a brace
  // inside a caption does not truncate the object.
  const extracted = firstBalanced(trimmed);
  if (extracted) return JSON.parse(extracted);

  throw new Error('No JSON object found in model output');
}

function firstBalanced(text: string): string | null {
  const start = text.search(/[{[]/);
  if (start === -1) return null;

  const openChar = text[start];
  const closeChar = openChar === '{' ? '}' : ']';
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (ch === '\\') {
      escaped = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (ch === openChar) depth++;
    else if (ch === closeChar) {
      depth--;
      if (depth === 0) return text.slice(start, i + 1);
    }
  }
  return null;
}
