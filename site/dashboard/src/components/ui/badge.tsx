import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap transition-colors",
  {
    variants: {
      variant: {
        default: "border-border bg-surface-2 text-muted",
        green: "border-[var(--green-dim)] bg-[color:rgba(34,197,94,0.12)] text-green",
        amber: "border-[#854d0e] bg-[color:rgba(251,191,36,0.12)] text-amber",
        danger: "border-[#7f1d1d] bg-[color:rgba(248,113,113,0.12)] text-danger",
        outline: "border-border bg-transparent text-text",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
