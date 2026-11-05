import { StatusIcon } from "@/components/icons/app-icons";

import type { NavigationItem, NavigationSection } from "./navigation-types";

export const NAVIGATION_SECTIONS: NavigationSection[] = [
  {
    id: "administration",
    label: "Administración",
  },
];

export const NAVIGATION_ITEMS: NavigationItem[] = [
  {
    href: "/system/status",
    label: "Estado del sistema",
    section: "administration",
    icon: StatusIcon,
    adminOnly: true,
  },
];
