import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, forwardRef } from "react";

const styles = cva(
  "inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 text-sm transition disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        solid: "bg-[var(--ink)] text-[#1a1612] hover:bg-white",
        ghost: "border border-[var(--line)] bg-white/5 hover:bg-white/10",
        gold: "bg-[var(--gold)] text-[#24180f] hover:brightness-110",
      },
    },
    defaultVariants: { variant: "solid" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof styles> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant, ...props },
  ref,
) {
  return <button ref={ref} className={cn(styles({ variant }), className)} {...props} />;
});
