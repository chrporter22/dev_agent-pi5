// ============================================================================
// STATIC + API PROXY SERVER — core/pca-backend/serve.mjs
// Serves the React bundle built into dist/ and proxies /api/* to node-api.
// Runs on port 80 inside the container; identical ingress contract to the
// old nginx setup so the frontend and node-api need no changes.
// ============================================================================

import { createServer } from "node:http"
import { createReadStream, statSync } from "node:fs"
import { extname, join, normalize, resolve } from "node:path"
import { pipeline } from "node:stream/promises"
import { createGzip, constants as zlibConstants } from "node:zlib"

const PORT = parseInt(process.env.PORT || "80", 10)
const UPSTREAM = process.env.NODE_API_URL || "http://node-api:3000"
const DIST_DIR = resolve(process.cwd(), "dist")

// ----------------------------------
// MIME
// ----------------------------------
const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js":   "application/javascript; charset=utf-8",
  ".mjs":  "application/javascript; charset=utf-8",
  ".css":  "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg":  "image/svg+xml",
  ".png":  "image/png",
  ".jpg":  "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif":  "image/gif",
  ".webp": "image/webp",
  ".ico":  "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf":  "font/ttf",
  ".map":  "application/json; charset=utf-8",
  ".txt":  "text/plain; charset=utf-8"
}

const COMPRESSIBLE = new Set([
  "text/html", "text/css", "application/javascript",
  "application/json", "image/svg+xml", "text/plain"
])

const INDEX_FALLBACK = join(DIST_DIR, "index.html")

// ----------------------------------
// STATIC FILE SERVING
// ----------------------------------
function resolveSafe(urlPath) {
  const rel = urlPath === "/" ? "/index.html" : urlPath
  const candidate = normalize(join(DIST_DIR, rel))
  if (!candidate.startsWith(DIST_DIR)) return null
  return candidate
}

async function sendStatic(req, res, filePath, acceptEncoding) {
  let stat
  try {
    stat = statSync(filePath)
  } catch {
    return false
  }

  if (stat.isDirectory()) {
    filePath = join(filePath, "index.html")
    try {
      stat = statSync(filePath)
    } catch {
      return false
    }
  }

  const ext = extname(filePath).toLowerCase()
  const type = MIME[ext] || "application/octet-stream"
  const compress = COMPRESSIBLE.has(type.split(";")[0]) &&
                   acceptEncoding && acceptEncoding.includes("gzip")

  res.writeHead(200, {
    "Content-Type": type,
    "Cache-Control": ext === ".html" ? "no-cache" : "public, max-age=3600",
    "Vary": "Accept-Encoding",
    "X-Content-Type-Options": "nosniff"
  })

  try {
    if (compress) {
      res.setHeader("Content-Encoding", "gzip")
      await pipeline(createReadStream(filePath), createGzip({
        level: zlibConstants.Z_BEST_SPEED
      }), res)
    } else {
      await pipeline(createReadStream(filePath), res)
    }
    return true
  } catch {
    return false
  }
}

async function sendIndex(res, acceptEncoding) {
  const stat = statSync(INDEX_FALLBACK)
  const compress = acceptEncoding && acceptEncoding.includes("gzip")
  res.writeHead(200, {
    "Content-Type": MIME[".html"],
    "Cache-Control": "no-cache",
    "Vary": "Accept-Encoding",
    "X-Content-Type-Options": "nosniff"
  })
  if (compress) {
    res.setHeader("Content-Encoding", "gzip")
    return pipeline(createReadStream(INDEX_FALLBACK), createGzip(), res)
  }
  return pipeline(createReadStream(INDEX_FALLBACK), res)
}

function send404(res) {
  res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" })
  res.end("Not found")
}

// ----------------------------------
// /api/* PROXY
// ----------------------------------
function proxyToNodeApi(req, res) {
  const target = new URL(UPSTREAM + req.url)

  const proxyReq = createRequest(
    target,
    {
      method: req.method,
      headers: {
        ...req.headers,
        host: target.host,
        "x-forwarded-host": req.headers.host || "",
        "x-forwarded-for": req.headers["x-forwarded-for"]
          ? `${req.headers["x-forwarded-for"]}, ${req.socket.remoteAddress}`
          : (req.socket.remoteAddress || "")
      }
    },
    upstreamRes => {
      const headers = { ...upstreamRes.headers }
      delete headers["content-length"]
      delete headers["content-encoding"]
      res.writeHead(upstreamRes.statusCode || 502, headers)
      pipeline(upstreamRes, res).catch(() => {})
    }
  )

  proxyReq.on("error", () => {
    if (!res.headersSent) {
      res.writeHead(502, { "Content-Type": "text/plain; charset=utf-8" })
      res.end("Bad gateway")
    } else {
      res.destroy()
    }
  })

  req.on("aborted", () => proxyReq.destroy())
  pipeline(req, proxyReq).catch(() => {})
}

// importable for tests; identical to http.request but scoped per call
import { request as createRequest } from "node:http"

// ----------------------------------
// SERVER
// ----------------------------------
const server = createServer(async (req, res) => {
  const url = new URL(req.url || "/", "http://x")
  const acceptEncoding = req.headers["accept-encoding"] || ""

  // /api/* → node-api
  if (url.pathname.startsWith("/api/")) {
    return proxyToNodeApi(req, res)
  }

  // HEAD/GET only for everything else
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405, { "Allow": "GET, HEAD" })
    res.end("Method not allowed")
    return
  }

  // Try static asset; fall back to SPA index.html
  const candidate = resolveSafe(url.pathname)
  if (candidate) {
    const ok = await sendStatic(req, res, candidate, acceptEncoding).catch(() => false)
    if (!ok) {
      sendIndex(res, acceptEncoding).catch(() => res.destroy())
    }
    return
  }

  sendIndex(res, acceptEncoding).catch(() => res.destroy())
})

server.listen(PORT, () => {
  console.log(
    `[pca-backend] listening on :${PORT}, proxying /api/* → ${UPSTREAM}`
  )
})
