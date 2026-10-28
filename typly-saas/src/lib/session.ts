import { getServerSession } from "next-auth";
import { authOptions } from "./auth";

export interface SessionUser {
  id: string;
  workspaceId: string;
  role: string;
}

export async function getSessionUser(): Promise<SessionUser | null> {
  const session = await getServerSession(authOptions);
  const u = session?.user as
    | { id?: string; workspaceId?: string; role?: string }
    | undefined;
  if (!u?.id || !u.workspaceId) return null;
  return { id: u.id, workspaceId: u.workspaceId, role: u.role ?? "WRITER" };
}

export async function requireSession(): Promise<SessionUser> {
  const u = await getSessionUser();
  if (!u) throw new Error("UNAUTHORIZED");
  return u;
}

export function canEdit(role: string): boolean {
  return role === "OWNER" || role === "ADMIN" || role === "WRITER";
}

export function canManage(role: string): boolean {
  return role === "OWNER" || role === "ADMIN";
}