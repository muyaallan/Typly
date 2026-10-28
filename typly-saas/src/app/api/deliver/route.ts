import { NextResponse } from "next/server";
import { getSessionUser, canEdit } from "@/lib/session";
import { prisma } from "@/lib/prisma";

type Method = "clipboard" | "download" | "webhook" | "agent";

interface Payload {
  documentId: string;
  method: Method;
  options?: { webhookUrl?: string };
}

export async function POST(req: Request) {
  const user = await getSessionUser();
  if (!user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  if (!canEdit(user.role)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  const body = (await req.json()) as Payload;
  const doc = await prisma.document.findUnique({
    where: { id: body.documentId },
  });
  if (!doc || doc.workspaceId !== user.workspaceId) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  const started = Date.now();
  let status = "ok";
  let message = "";

  try {
    switch (body.method) {
      case "clipboard":
      case "download":
      case "agent":
        message = "Queued client-side";
        break;
      case "webhook": {
        const url = body.options?.webhookUrl;
        if (!url) throw new Error("webhookUrl required");
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: doc.title,
            content: doc.content,
            docType: doc.docType,
          }),
        });
        message = `Webhook ${res.status}`;
        if (!res.ok) status = "failed";
        break;
      }
      default:
        throw new Error("Unknown method");
    }
  } catch (e) {
    status = "failed";
    message = String(e);
  }

  await prisma.delivery.create({
    data: {
      workspaceId: user.workspaceId,
      documentId: doc.id,
      method: body.method,
      status,
      message,
      durationMs: Date.now() - started,
    },
  });

  return NextResponse.json({ status, message });
}