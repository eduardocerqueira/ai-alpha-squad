import { readFileSync } from "node:fs";
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const JOBS_JSON = path.resolve(__dirname, "../public/director/jobs.json");
const VERSION_FILE = path.resolve(__dirname, "../VERSION");

// Same version shown in the marketing-site footer (site/VERSION, synced by
// scripts/sync-site-version.py). Baked in at build time so the dashboard header
// and sidebar footer always match the homepage without a runtime fetch.
function readVersion(): string {
  try {
    return readFileSync(VERSION_FILE, "utf-8").trim() || "0.0.0";
  } catch {
    return "0.0.0";
  }
}

// In `npm run dev` the data file lives outside the Vite project root, so the
// dev server would 404 → SPA-fallback to index.html and the app's fetch() would
// receive HTML. Serve the real snapshot for both the live endpoint the app
// calls (/api/director/jobs) and the static path (/director/jobs.json).
function serveJobsJson(): Plugin {
  const handler = (_req: unknown, res: import("node:http").ServerResponse) => {
    try {
      res.setHeader("Content-Type", "application/json");
      res.setHeader("Cache-Control", "no-store");
      res.end(readFileSync(JOBS_JSON));
    } catch {
      res.statusCode = 404;
      res.end(JSON.stringify({ error: "jobs.json not found — run ./scripts/squad-director-dashboard.py --write" }));
    }
  };
  const jsonRes = (res: import("node:http").ServerResponse, obj: unknown) => {
    res.setHeader("Content-Type", "application/json");
    res.setHeader("Cache-Control", "no-store");
    res.end(JSON.stringify(obj));
  };
  return {
    name: "serve-director-jobs-json",
    configureServer(server) {
      server.middlewares.use("/api/director/jobs", handler);
      server.middlewares.use("/director/jobs.json", handler);
      // Dev stub for /api/config (version + a sample model ladder for the retry UI).
      server.middlewares.use("/api/config", (_req, res) =>
        jsonRes(res, {
          version: readVersion(),
          modelLadder: [
            "deepseek-ai/DeepSeek-V4-Flash",
            "Qwen/Qwen3-Coder-480B-A35B-Instruct",
            "moonshotai/Kimi-K2-Instruct",
          ],
        }),
      );
      // Dev auth stub: signed in as a local dev user so login is skipped.
      server.middlewares.use("/api/director/auth/me", (_req, res) =>
        jsonRes(res, { email: "dev@localhost" }),
      );
      server.middlewares.use("/api/director/auth/request", (_req, res) =>
        jsonRes(res, { ok: true }),
      );
      server.middlewares.use("/api/director/auth/logout", (_req, res) => jsonRes(res, { ok: true }));
      // Dev stubs for retry/stop so the buttons can be exercised locally.
      server.middlewares.use("/api/director/retry", (_req, res) => jsonRes(res, { ok: true }));
      server.middlewares.use("/api/director/stop", (_req, res) =>
        jsonRes(res, { ok: true, cancelled: 1, agent: "developer" }),
      );
    },
  };
}

// Built to the Worker's static assets dir so the existing Cloudflare Worker
// (site/) serves the dashboard at /director/ with no extra routing.
export default defineConfig({
  base: "/director/",
  define: {
    __APP_VERSION__: JSON.stringify(readVersion()),
  },
  plugins: [react(), serveJobsJson()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  build: {
    outDir: path.resolve(__dirname, "../public/director"),
    // Do NOT wipe the dir — jobs.json lives here and is refreshed by CI.
    emptyOutDir: false,
    assetsDir: "assets",
  },
});
