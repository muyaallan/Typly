import { type DocType } from "./document-types";

function validJson(text: string): boolean {
  try {
    JSON.parse(text);
    return true;
  } catch {
    return false;
  }
}

const DETECTORS: [DocType, (t: string) => boolean][] = [
  ["json",     (t) => /^[\[{]/.test(t.trim()) && validJson(t)],
  ["latex",    (t) => /\\[a-zA-Z]+\{/.test(t)],
  ["html",     (t) => /<\/?[a-zA-Z][^>]*>/.test(t)],
  ["sql",      (t) => /\b(SELECT|INSERT|UPDATE|DELETE|CREATE)\b/i.test(t)],
  ["code",     (t) => /^\s*(def |class |function |import |from |const |let |var |fn |pub fn |#include|package )/m.test(t)],
  ["markdown", (t) => /^(#{1,6} |\* |\- |\d+\. |```)/m.test(t)],
  ["yaml",     (t) => /^[a-zA-Z_][\w-]*:\s/m.test(t)],
];

export function detectType(text: string): DocType {
  if (!text.trim()) return "plain";
  for (const [type, pred] of DETECTORS) {
    try {
      if (pred(text)) return type;
    } catch {
      continue;
    }
  }
  return "plain";
}