import type { Issue } from "./types";

export function validateJson(content: string): Issue[] {
  try {
    JSON.parse(content);
    return [];
  } catch (e) {
    const err = e as SyntaxError;
    const match = /position (\d+)/.exec(err.message);
    let line: number | undefined;
    if (match) {
      const pos = parseInt(match[1], 10);
      line = content.slice(0, pos).split("\n").length;
    }
    return [{ severity: "error", message: `JSON: ${err.message}`, line }];
  }
}