import type { NextConfig } from "next";

// Destination for the /api/* proxy. Each developer sets this in .env.local.
// Defaults to localhost:8000 so the solo-machine setup works with no config.
const API_HOST = process.env.NEXT_PUBLIC_API_HOST ?? "http://localhost:8000";

const nextConfig: NextConfig = {
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
