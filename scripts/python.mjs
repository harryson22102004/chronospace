import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const python =
  process.env.PYTHON ||
  (process.platform === "win32"
    ? resolve(".venv", "Scripts", "python.exe")
    : resolve(".venv", "bin", "python"));
const result = spawnSync(python, process.argv.slice(2), { stdio: "inherit" });

if (result.error) {
  console.error(`Unable to run Python at ${python}: ${result.error.message}`);
  process.exit(1);
}

process.exit(result.status ?? 1);
