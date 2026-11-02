"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";

export function Slider({
  value,
  min = 0,
  max = 1,
  step = 0.01,
  onValueChange,
  label,
}: {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onValueChange: (value: number) => void;
  label: string;
}) {
  return (
    <label className="block">
      <span className="mb-2 flex items-center justify-between text-xs text-[var(--muted)]">
        <span>{label}</span>
        <span>{value.toFixed(2)}</span>
      </span>
      <SliderPrimitive.Root
        className="relative flex h-5 w-full touch-none items-center"
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={(next) => onValueChange(next[0] ?? value)}
      >
        <SliderPrimitive.Track className="relative h-px grow bg-white/20">
          <SliderPrimitive.Range className="absolute h-px bg-[var(--gold)]" />
        </SliderPrimitive.Track>
        <SliderPrimitive.Thumb className="block h-3.5 w-3.5 rounded-full bg-[var(--ink)] shadow" />
      </SliderPrimitive.Root>
    </label>
  );
}
