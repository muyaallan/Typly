import type { LucideIcon } from "lucide-react";
import {
  Home,
  FileText,
  PenLine,
  LayoutTemplate,
  Zap,
  Radio,
  Workflow,
  Send,
  Download,
  Clipboard,
  BarChart3,
  History,
  ScrollText,
  Monitor,
  Settings,
  HelpCircle,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
}

export interface NavGroup {
  heading: string | null;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    heading: null,
    items: [
      { label: "Home", href: "/dashboard", icon: Home },
    ],
  },
  {
    heading: "WRITE",
    items: [
      { label: "Documents", href: "/documents", icon: FileText },
      { label: "Editor",    href: "/editor",    icon: PenLine },
      { label: "Templates", href: "/templates", icon: LayoutTemplate },
    ],
  },
  {
    heading: "AUTOMATE",
    items: [
      { label: "Automations", href: "/automations", icon: Zap },
      { label: "Triggers",    href: "/triggers",    icon: Radio },
      { label: "Workflows",   href: "/workflows",   icon: Workflow },
    ],
  },
  {
    heading: "DELIVER",
    items: [
      { label: "Deliver",   href: "/deliver",   icon: Send },
      { label: "Export",    href: "/export",    icon: Download },
      { label: "Clipboard", href: "/clipboard", icon: Clipboard },
    ],
  },
  {
    heading: "INSIGHTS",
    items: [
      { label: "Analytics", href: "/analytics", icon: BarChart3 },
      { label: "History",   href: "/history",   icon: History },
      { label: "Logs",      href: "/logs",      icon: ScrollText },
    ],
  },
  {
    heading: "SYSTEM",
    items: [
      { label: "Devices",  href: "/devices",  icon: Monitor },
      { label: "Settings", href: "/settings", icon: Settings },
      { label: "Help",     href: "/help",     icon: HelpCircle },
    ],
  },
];