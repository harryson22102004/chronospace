"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";

export function Switch({
  checked,
  onCheckedChange,
  label,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center justify-between gap-3 text-sm">
      <span>{label}</span>
      <SwitchPrimitive.Root
        checked={checked}
        onCheckedChange={onCheckedChange}
        className="relative h-6 w-10 rounded-full bg-white/15 data-[state=checked]:bg-[var(--gold)]"
      >
        <SwitchPrimitive.Thumb className="block h-5 w-5 translate-x-0.5 rounded-full bg-[#1a1612] transition data-[state=checked]:translate-x-4" />
      </SwitchPrimitive.Root>
    </label>
  );
}
