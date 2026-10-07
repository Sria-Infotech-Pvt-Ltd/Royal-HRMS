import type { NextConfig } from "next";

// Destination for the /api/* proxy. Each developer sets this in .env.local.
// Defaults to localhost:8000 so the solo-machine setup works with no config.
const API_HOST = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Pins the workspace root to this directory. Without this, Turbopack walks
  // up looking for lockfiles and finds the repo-root package-lock.json above
  // frontend/ too, so it guesses the wrong root and warns on every dev/build.
  turbopack: {
    root: __dirname,
  },
  // Prevent Next.js from 308-redirecting /api/login/ → /api/login before the
  // rewrite runs. Without this, Django's APPEND_SLASH raises a RuntimeError on
  // POST because it cannot redirect and preserve the request body.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_HOST}/api/:path*/`,
      },
    ];
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "res.cloudinary.com",
      },
    ],
  },
  async headers() {
    return [
      {
        // Face-api.js weights (~7 MB) are pinned to a specific commit (see
        // public/models/README.md) and never change in place, so let browsers
        // and any CDN/proxy keep them instead of re-validating on every page
        // load (Next's default for public/ files is max-age=0). If the weights
        // are ever replaced, rename the files or shorten this.
        source: "/models/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=2592000, stale-while-revalidate=86400" },
        ],
      },
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options",           value: "DENY" },
          { key: "X-Content-Type-Options",     value: "nosniff" },
          { key: "Referrer-Policy",            value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
