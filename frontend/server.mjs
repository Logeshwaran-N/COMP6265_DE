import http from "node:http";
import { createReadStream, existsSync, statSync } from "node:fs";
import { join, extname, normalize } from "node:path";

const candidates = [join(process.cwd(), "dist"), join(process.cwd(), "frontend", "dist")];
const root = candidates.find((p) => existsSync(join(p, "index.html"))) || candidates[0];
const port = Number(process.env.PORT || 5173);
const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".ico": "image/x-icon"
};

function safePath(urlPath) {
  const decoded = decodeURIComponent((urlPath || "/").split("?")[0]);
  const clean = normalize(decoded).replace(/^([.][.][\/\\])+/, "");
  return join(root, clean === "/" ? "index.html" : clean);
}

const server = http.createServer((req, res) => {
  let filePath = safePath(req.url || "/");
  if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
    filePath = join(root, "index.html");
  }
  const ext = extname(filePath);
  res.setHeader("Content-Type", types[ext] || "application/octet-stream");
  res.setHeader("Cache-Control", ext === ".html" ? "no-cache" : "public, max-age=31536000, immutable");
  createReadStream(filePath).on("error", () => {
    res.statusCode = 404;
    res.end("Not found");
  }).pipe(res);
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Frontend serving ${root} on port ${port}`);
});
