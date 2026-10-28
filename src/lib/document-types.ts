export const DOC_TYPES = [
  "plain", "markdown", "code", "json", "yaml",
  "html", "latex", "sql", "email", "social",
] as const;

export type DocType = (typeof DOC_TYPES)[number];

export const DOC_TYPE_LABELS: Record<DocType, string> = {
  plain: "Plain Text",
  markdown: "Markdown",
  code: "Code",
  json: "JSON",
  yaml: "YAML",
  html: "HTML",
  latex: "LaTeX",
  sql: "SQL",
  email: "Email",
  social: "Social",
};