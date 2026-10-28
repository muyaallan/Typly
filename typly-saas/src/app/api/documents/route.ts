import { NextResponse } from "next/server";
import { getSessionUser } from "@/lib/session";
import { prisma } from "@/lib/prisma";

export async function GET(req: Request) {
  const user = await getSessionUser();
  if (!user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(req.url);
  const q = searchParams.get("q")?.toLowerCase() ?? "";
  const docType = searchParams.get("type") ?? undefined;
  const sort = searchParams.get("sort") ?? "modified";
  const projectId = searchParams.get("projectId") ?? undefined;

  const docs = await prisma.document.findMany({
    where: {
      workspaceId: user.workspaceId,
      ...(docType ? { docType } : {}),
      ...(projectId ? { projectId } : {}),
      ...(q
        ? {
            OR: [
              { title:   { contains: q } },
              { content: { contains: q } },
            ],
          }
        : {}),
    },
    orderBy:
      sort === "title"   ? { title: "asc" }      :
      sort === "created" ? { created: "desc" }   :
      sort === "words"   ? { wordCount: "desc" } :
      { modified: "desc" },
    take: 200,
  });

  return NextResponse.json(docs);
}

export async function POST() {
  const user = await getSessionUser();
  if (!user) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const doc = await prisma.document.create({
    data: {
      workspaceId: user.workspaceId,
      authorId: user.id,
      title: "Untitled Document",
      content: "",
      docType: "plain",
    },
  });

  return NextResponse.json(doc);
}