import type { Issue } from "./types";

export function validateMarkdown(content: string): Issue[] {
  const issues: Issue[] = [];
  const fences = (content.match(/```/g) || []).length;
  if (fences % 2) {
    issues.push({
      severity: "warning",
      message: "Odd number of ``` fences - possible unclosed block",
    });
  }
  content.split("\n").forEach((line, i) => {
    if (/^#{1,6}[^#\s]/.test(line)) {
      issues.push({
        severity: "warning",
        message: "Missing space after heading marker",
        line: i + 1,
      });
    }
  });
  return issues;
}