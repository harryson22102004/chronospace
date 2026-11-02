import { spawn } from "node:child_process";

const python = process.env.PYTHON || ".venv/bin/python";
const vision = spawn(
  python,
  ["-m", "uvicorn", "services.epistemic.server:app", "--host", "127.0.0.1", "--port", "8742"],
  { stdio: "inherit" },
);
const web = spawn("npx", ["next", "dev", "--turbopack", "-H", "0.0.0.0", "-p", "43123"], {
  stdio: "inherit",
});

function stop() {
  vision.kill("SIGTERM");
  web.kill("SIGTERM");
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
vision.on("exit", (code) => {
  if (code) process.exit(code);
});
web.on("exit", (code) => process.exit(code ?? 0));
