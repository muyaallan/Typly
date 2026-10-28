import { NextResponse } from "next/server";
import { getSessionUser, canEdit } from "@/lib/session";
import { prisma } from "@/lib/prisma";

type RouteContext = { params: Promise<{ id: string }> };

async function loadOwned(id: string, workspaceId: string) {
  const doc = await prisma.document.findUnique({ where: { id } });
  if (!doc || doc.workspaceId !== workspaceId) return null;
  return doc;
}

export async function GET(_: Request, ctx: RouteContext) {
  const { id } = await ctx.params;
  const user = await getSessionUser();
  if (!user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const doc = await loadOwned(id, user.workspaceId);
  if (!doc) return NextResponse.json({ error: "not found" }, { status: 404 });
  return NextResponse.json(doc);
}

export async function PATCH(req: Request, ctx: RouteContext) {
  const { id } = await ctx.params;
  const user = await getSessionUser();
  if (!user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  if (!canEdit(user.role)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  const doc = await loadOwned(id, user.workspaceId);
  if (!doc) return NextResponse.json({ error: "not found" }, { status: 404 });

  const body = await req.json();
  const { title, content, docType, autoType } = body;

  const wordCount = typeof content === "string"
    ? content.split(/\s+/).filter(Boolean).length
    : undefined;
  const charCount = typeof content === "string" ? content.length : undefined;

  const updated = await prisma.document.update({
    where: { id },
    data: {
      ...(title !== undefined ? { title } : {}),
      ...(content !== undefined ? { content, wordCount, charCount } : {}),
      ...(docType !== undefined ? { docType } : {}),
      ...(autoType !== undefined ? { autoType } : {}),
    },
  });

  return NextResponse.json(updated);
}

export async function DELETE(_: Request, ctx: RouteContext) {
  const { id } = await ctx.params;
  const user = await getSessionUser();
  if (!user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  if (!canEdit(user.role)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }
  const doc = await loadOwned(id, user.workspaceId);
  if (!doc) return NextResponse.json({ error: "not found" }, { status: 404 });

  await prisma.document.delete({ where: { id } });
  return NextResponse.json({ ok: true });
}