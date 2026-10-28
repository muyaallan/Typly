export interface DocumentDTO {
  id: string;
  title: string;
  content: string;
  docType: string;
  autoType: boolean;
  metadata: string;
  wordCount: number;
  charCount: number;
  created: string;
  modified: string;
  workspaceId: string;
  projectId: string | null;
  authorId: string;
}

export interface DeliveryDTO {
  id: string;
  documentId: string;
  method: string;
  status: string;
  message: string | null;
  durationMs: number | null;
  createdAt: string;
}