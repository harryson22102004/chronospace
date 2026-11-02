/** Depth is stored normalized, 1 = closest. Displacement moves that point toward the camera. */

export function closerMeansHigherZ(normalizedDepth: number, scale: number): number {
  return normalizedDepth * scale;
}

export function planeSize(width: number, height: number, planeWidth = 1.7) {
  return { width: planeWidth, height: planeWidth * (height / width) };
}
