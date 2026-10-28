import { create } from "zustand";
import type { DocType } from "@/lib/document-types";
import type { ValidationResult } from "@/lib/validation/types";

export type SaveStatus = "saved" | "unsaved" | "saving" | "error";

interface EditorState {
  docId: string | null;
  title: string;
  content: string;
  docType: DocType;
  autoType: boolean;
  saveStatus: SaveStatus;
  validation: ValidationResult | null;

  load: (payload: {
    docId: string;
    title: string;
    content: string;
    docType: DocType;
    autoType: boolean;
  }) => void;
  setTitle: (title: string) => void;
  setContent: (content: string) => void;
  setDocType: (docType: DocType) => void;
  setSaveStatus: (status: SaveStatus) => void;
  setValidation: (v: ValidationResult | null) => void;
  reset: () => void;
}

export const useEditorStore = create<EditorState>((set) => ({
  docId: null,
  title: "",
  content: "",
  docType: "plain",
  autoType: true,
  saveStatus: "saved",
  validation: null,

  load: (p) => set({
    docId: p.docId,
    title: p.title,
    content: p.content,
    docType: p.docType,
    autoType: p.autoType,
    saveStatus: "saved",
    validation: null,
  }),
  setTitle: (title) => set({ title, saveStatus: "unsaved" }),
  setContent: (content) => set({ content, saveStatus: "unsaved" }),
  setDocType: (docType) => set({ docType, autoType: false, saveStatus: "unsaved" }),
  setSaveStatus: (saveStatus) => set({ saveStatus }),
  setValidation: (validation) => set({ validation }),
  reset: () => set({
    docId: null, title: "", content: "", docType: "plain",
    autoType: true, saveStatus: "saved", validation: null,
  }),
}));