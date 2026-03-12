import type { NextConfig } from "next";

const OPS_API_PROXY_TARGET = process.env.OPS_API_PROXY_TARGET ?? "http://127.0.0.1:18082";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${OPS_API_PROXY_TARGET}/api/:path*`
      }
    ];
  }
};

export default nextConfig;
