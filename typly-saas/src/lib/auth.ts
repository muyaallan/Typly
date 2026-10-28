import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import { prisma } from "./prisma";

function slugify(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40) || "workspace";
}

async function uniqueSlug(base: string): Promise<string> {
  let slug = base;
  let n = 1;
  while (await prisma.workspace.findUnique({ where: { slug } })) {
    n += 1;
    slug = `${base}-${n}`;
  }
  return slug;
}

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  providers: [
    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        name:  { label: "Name",  type: "text"  },
      },
      async authorize(credentials) {
        if (!credentials?.email) return null;
        const email = credentials.email.toLowerCase().trim();

        let user = await prisma.user.findUnique({ where: { email } });

        if (!user) {
          // First-time signup: create user + personal workspace + owner membership
          const displayName =
            credentials.name?.trim() || email.split("@")[0];

          user = await prisma.user.create({
            data: {
              email,
              name: displayName,
              memberships: {
                create: {
                  role: "OWNER",
                  workspace: {
                    create: {
                      name: `${displayName}'s Workspace`,
                      slug: await uniqueSlug(slugify(displayName)),
                      isPersonal: true,
                      subscription: {
                        create: { plan: "FREE", status: "active", seats: 1 },
                      },
                    },
                  },
                },
              },
            },
          });
        }

        return { id: user.id, email: user.email, name: user.name };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.uid = (user as { id: string }).id;
        // Load active workspace for the session
        const membership = await prisma.membership.findFirst({
          where: { userId: (user as { id: string }).id },
          orderBy: { createdAt: "asc" },
          include: { workspace: true },
        });
        if (membership) {
          token.wid = membership.workspaceId;
          token.role = membership.role;
        }
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user && token.uid) {
        (session.user as { id: string }).id = token.uid as string;
      }
      if (session.user && token.wid) {
        (session.user as { workspaceId: string }).workspaceId =
          token.wid as string;
        (session.user as { role: string }).role =
          (token.role as string) ?? "WRITER";
      }
      return session;
    },
  },
  pages: { signIn: "/signin" },
  secret: process.env.NEXTAUTH_SECRET,
};