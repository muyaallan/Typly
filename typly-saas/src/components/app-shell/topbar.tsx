"use client";

import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { NAV_GROUPS } from "./nav-groups";

interface TopbarProps {
  onMenuClick?: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const pathname = usePathname();
  const title = deriveTitle(pathname);

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background px-4">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={onMenuClick}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </Button>

      <h1 className="text-sm font-semibold tracking-tight">{title}</h1>

      <div className="ml-auto flex items-center gap-2">
        <div className="rounded-md border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground">
          Personal Workspace
        </div>
      </div>
    </header>
  );
}

function deriveTitle(pathname: string): string {
  const segment = pathname.split("/").filter(Boolean)[0] ?? "";
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      if (item.href === `/${segment}`) return item.label;
    }
  }
  if (segment === "") return "Home";
  return segment.charAt(0).toUpperCase() + segment.slice(1);
}