import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** "https://github.com/o/r/pull/6" → " #6" (leading space for inline use); "" if none. */
export function prNumber(url: string | null | undefined): string {
  const m = url?.match(/\/pull\/(\d+)/);
  return m ? ` #${m[1]}` : "";
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diff = Date.now() - then;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

/** "deepseek-ai/DeepSeek-V4-Flash" → "DeepSeek-V4-Flash" (drop the org prefix). */
export function modelShort(model: string | null | undefined): string {
  if (!model) return "";
  return model.includes("/") ? model.split("/").pop()! : model;
}

/** Absolute date + time, e.g. "Jun 1, 23:38" (locale-formatted); "" if invalid. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
