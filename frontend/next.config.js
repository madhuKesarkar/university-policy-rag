/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxies /api/* to the FastAPI backend server-side, so the browser only ever talks to this
  // same origin. Simpler than CORS for local dev, and the same pattern works in production
  // behind a reverse proxy (set BACKEND_URL to the deployed API's internal address).
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://127.0.0.1:8000"}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
