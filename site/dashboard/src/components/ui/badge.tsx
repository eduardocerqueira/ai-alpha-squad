import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap transition-colors focus:outline-none",
  {
    variants: {
      variant: {
        default: "border-border bg-secondary text-muted-foreground",
        green: "border-brand-green-dim bg-brand-green/12 text-brand-green",
        amber: "border-brand-amber/40 bg-brand-amber/12 text-brand-amber",
        danger: "border-brand-danger/40 bg-brand-danger/12 text-brand-danger",
        outline: "border-border bg-transparent text-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
