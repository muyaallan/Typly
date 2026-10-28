"use client";

import { useEffect, useRef } from "react";
import { useEditorStore } from "@/store/editor-store";
import { detectType } from "@/lib/detect-type";

interface Options {
  delayMs?: number;
  onSaved?: () => void;
  onError?: (err: unknown) => void;
}

export function useAutosave({ delayMs = 1200, onSaved, onError }: Options = {}) {
  const {
    docId, title, content, docType, autoType, saveStatus,
    setSaveStatus, setDocType,
  } = useEditorStore();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!docId || saveStatus !== "unsaved") return;

    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      try {
        setSaveStatus("saving");

        let effectiveType = docType;
        if (autoType) {
          effectiveType = detectType(content);
          if (effectiveType !== docType) setDocType(effectiveType);
        }

        const res = await fetch(`/api/documents/${docId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, content, docType: effectiveType, autoType }),
        });

        if (!res.ok) throw new Error(await res.text());
        setSaveStatus("saved");
        onSaved?.();
      } catch (err) {
        setSaveStatus("error");
        onError?.(err);
      }
    }, delayMs);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [docId, title, content, docType, autoType, saveStatus,
      delayMs, setSaveStatus, setDocType, onSaved, onError]);
}