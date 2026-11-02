export const VISION_URL = process.env.VISION_URL || "http://127.0.0.1:8742";

export async function vision(path: string, init?: RequestInit) {
  return fetch(`${VISION_URL}${path}`, { ...init, cache: "no-store" });
}
