import type { DocType } from "../document-types";
import type { Issue, ValidationResult } from "./types";
import { validateJson } from "./json";
import { validateMarkdown } from "./markdown";
import { validateYaml } from "./yaml";

function validateUnicode(content: string): Issue[] {
  const issues: Issue[] = [];
  content.split("\n").forEach((line, i) => {
    for (let j = 0; j < line.length; j++) {
      const cp = line.codePointAt(j);
      if (cp && cp > 0xffff) {
        issues.push({
          severity: "warning",
          message: `Non-BMP character U+${cp.toString(16).toUpperCase()} may not type correctly`,
          line: i + 1,
          col: j,
        });
        break;
      }
    }
  });
  return issues;
}

function validateCode(content: string): Issue[] {
  const issues: Issue[] = [];
  content.split("\n").forEach((line, i) => {
    if (line.startsWith(" ") && line.includes("\t")) {
      issues.push({
        severity: "warning",
        message: "Mixed tabs and spaces",
        line: i + 1,
      });
    }
  });
  return issues;
}

const VALIDATORS: Record<DocType, ((c: string) => Issue[])[]> = {
  json:     [validateJson, validateUnicode],
  yaml:     [validateYaml, validateUnicode],
  markdown: [validateMarkdown, validateUnicode],
  code:     [validateCode, validateUnicode],
  html:     [validateUnicode],
  latex:    [validateUnicode],
  sql:      [validateUnicode],
  plain:    [validateUnicode],
  email:    [validateUnicode],
  social:   [validateUnicode],
};

export function validateContent(content: string, docType: DocType): ValidationResult {
  const validators = VALIDATORS[docType] ?? [validateUnicode];
  const issues: Issue[] = [];
  for (const fn of validators) {
    try {
      issues.push(...fn(content));
    } catch (e) {
      issues.push({ severity: "error", message: `Validator crashed: ${e}` });
    }
  }
  const ok = !issues.some((i) => i.severity === "error");
  return { ok, issues, checked: `${validators.length} validators` };
}