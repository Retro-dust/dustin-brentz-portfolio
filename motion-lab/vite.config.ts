import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, type PreviewServer, type ViteDevServer } from "vite";

const root = fileURLToPath(new URL(".", import.meta.url));
const siteRoot = path.resolve(root, "..");

function mime(file: string) {
  if (file.endsWith(".png")) return "image/png";
  if (file.endsWith(".jpg") || file.endsWith(".jpeg")) return "image/jpeg";
  if (file.endsWith(".webp")) return "image/webp";
  if (file.endsWith(".svg")) return "image/svg+xml";
  if (file.endsWith(".gif")) return "image/gif";
  if (file.endsWith(".pdf")) return "application/pdf";
  return "application/octet-stream";
}

function serveSiteStatic() {
  const handler = (
    req: { url?: string },
    res: NodeJS.WritableStream & { setHeader: (k: string, v: string) => void; statusCode: number },
    next: () => void,
  ) => {
    const url = (req.url ?? "").split("?")[0];
    if (!(url.startsWith("/assets/") || url === "/resume.pdf")) {
      next();
      return;
    }
    const file = path.resolve(siteRoot, url.slice(1));
    if (!file.startsWith(siteRoot) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
      next();
      return;
    }
    res.setHeader("Content-Type", mime(file));
    fs.createReadStream(file).pipe(res);
  };

  return {
    name: "serve-site-static",
    configureServer(server: ViteDevServer) {
      server.middlewares.use((req, res, next) => {
        handler(req, res as typeof res & { setHeader: (k: string, v: string) => void }, next);
      });
    },
    configurePreviewServer(server: PreviewServer) {
      server.middlewares.use((req, res, next) => {
        handler(req, res as typeof res & { setHeader: (k: string, v: string) => void }, next);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), serveSiteStatic()],
  base: "/lab/",
  build: {
    outDir: "../lab",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    host: true,
  },
});
