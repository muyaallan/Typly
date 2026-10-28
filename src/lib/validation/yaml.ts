import type { Issue } from "./types";

export function validateYaml(content: string): Issue[] {
  const issues: Issue[] = [];
  content.split("\n").forEach((line, i) => {
    if (/^\t/.test(line)) {
      issues.push({
        severity: "error",
        message: "YAML does not allow tabs for indentation",
        line: i + 1,
      });
    }
  });
  return issues;
}