import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `http://localhost:${process.env.API_PORT || "8001"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
