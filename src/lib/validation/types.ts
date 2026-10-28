export type Severity = "error" | "warning" | "info";

export interface Issue {
  severity: Severity;
  message: string;
  line?: number;
  col?: number;
}

export interface ValidationResult {
  ok: boolean;
  issues: Issue[];
  checked: string;
}