import { spawn } from "node:child_process";
import { resolve } from "node:path";

const python =
  process.env.PYTHON ||
  (process.platform === "win32"
    ? resolve(".venv", "Scripts", "python.exe")
    : resolve(".venv", "bin", "python"));
const next = resolve("node_modules", "next", "dist", "bin", "next");
const visionHost = process.env.VISION_HOST || "127.0.0.1";
const vision = spawn(
  python,
  ["-m", "uvicorn", "services.epistemic.server:app", "--host", visionHost, "--port", process.env.VISION_PORT || "8742"],
  { stdio: "inherit" },
);
const web = spawn(process.execPath, [next, "start", "-H", "0.0.0.0", "-p", process.env.PORT || "43123"], {
  stdio: "inherit",
  env: { ...process.env, VISION_URL: process.env.VISION_URL || "http://127.0.0.1:8742" },
});

function stop() {
  vision.kill("SIGTERM");
  web.kill("SIGTERM");
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
web.on("exit", (code) => process.exit(code ?? 0));
