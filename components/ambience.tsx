"use client";

import { useEffect } from "react";

export function useAmbience(elements: string[], enabled: boolean, volume: number) {
  useEffect(() => {
    if (!enabled) return;
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioCtx();
    const master = ctx.createGain();
    master.gain.value = volume;
    master.connect(ctx.destination);
    const timers: number[] = [];

    const noise = (gainValue: number, frequency: number) => {
      const buffer = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.loop = true;
      const filter = ctx.createBiquadFilter();
      filter.type = "lowpass";
      filter.frequency.value = frequency;
      const gain = ctx.createGain();
      gain.gain.value = gainValue;
      source.connect(filter).connect(gain).connect(master);
      source.start();
    };

    if (elements.includes("room tone")) noise(0.045, 380);
    if (elements.includes("wind")) noise(0.03, 900);
    if (elements.includes("rain")) noise(0.04, 2200);
    if (elements.includes("fireplace")) noise(0.05, 280);
    if (elements.includes("traffic") || elements.includes("crowd")) noise(0.02, 500);

    if (elements.includes("clock")) {
      const tick = window.setInterval(() => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = 1700;
        gain.gain.setValueAtTime(0.04, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.04);
        const pan = ctx.createStereoPanner();
        pan.pan.value = 0.35;
        osc.connect(gain).connect(pan).connect(master);
        osc.start();
        osc.stop(ctx.currentTime + 0.05);
      }, 1000);
      timers.push(tick);
    }

    if (elements.includes("distant birds")) {
      const chirp = window.setInterval(() => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(1200 + Math.random() * 700, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(2400, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.025, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
        const pan = ctx.createStereoPanner();
        pan.pan.value = Math.random() * 1.4 - 0.7;
        osc.connect(gain).connect(pan).connect(master);
        osc.start();
        osc.stop(ctx.currentTime + 0.22);
      }, 2600);
      timers.push(chirp);
    }

    return () => {
      timers.forEach((id) => window.clearInterval(id));
      void ctx.close();
    };
  }, [enabled, volume, elements]);
}
