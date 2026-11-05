import type { AuthUser } from "./types";

export type AppRole = "ADMIN" | "INVENTORY" | "SALES" | "CUSTOMERS" | "READ_ONLY";

export function isAdministrativeUser(user: AuthUser): boolean {
  return (
    user.is_superuser ||
    user.is_staff ||
    user.groups.includes("ADMIN")
  );
}
