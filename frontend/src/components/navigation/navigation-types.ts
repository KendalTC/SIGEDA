import type { ComponentType } from "react";

import type { AuthUser } from "@/features/auth/types";

export type NavigationSectionId = "administration";

export type NavigationIconComponent = ComponentType<{
  className?: string;
}>;

export type NavigationItem = {
  href: string;
  label: string;
  section: NavigationSectionId;
  icon: NavigationIconComponent;
  permissionCheck?: (user: AuthUser) => boolean;
  adminOnly?: boolean;
};

export type NavigationSection = {
  id: NavigationSectionId;
  label: string;
};
