// Remove prior build output from the Worker assets dir WITHOUT touching
// jobs.json (refreshed by CI). Runs before `vite build` (emptyOutDir is off
// so Vite never deletes jobs.json itself).
import { rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../public/director");
rmSync(path.join(dir, "assets"), { recursive: true, force: true });
rmSync(path.join(dir, "index.html"), { force: true });
console.log("cleaned stale dashboard build in", dir);
