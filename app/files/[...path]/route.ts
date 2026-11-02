import fs from "fs";
import path from "path";

const TYPES: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".webp": "image/webp",
};

export async function GET(_request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path: parts } = await context.params;
  const root = path.resolve(process.cwd(), "data");
  const target = path.resolve(root, ...parts);
  if (!target.startsWith(root + path.sep)) {
    return new Response("Forbidden", { status: 403 });
  }
  if (!fs.existsSync(target) || !fs.statSync(target).isFile()) {
    return new Response("Not found", { status: 404 });
  }
  const data = fs.readFileSync(target);
  const type = TYPES[path.extname(target).toLowerCase()] || "application/octet-stream";
  return new Response(data, { headers: { "Content-Type": type, "Cache-Control": "no-store" } });
}
