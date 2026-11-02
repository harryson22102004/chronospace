import { spawn } from "node:child_process";

const python = process.env.PYTHON || ".venv/bin/python";
const vision = spawn(
  python,
  ["-m", "uvicorn", "services.epistemic.server:app", "--host", "0.0.0.0", "--port", process.env.VISION_PORT || "8742"],
  { stdio: "inherit" },
);
const web = spawn("npx", ["next", "start", "-H", "0.0.0.0", "-p", process.env.PORT || "43123"], {
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
