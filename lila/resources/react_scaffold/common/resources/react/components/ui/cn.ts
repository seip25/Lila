/** Joins truthy class names: cn("btn", active && "active"). */
export function cn(...parts: Array<string | false | null | undefined | 0>): string {
  return parts.filter(Boolean).join(" ");
}
