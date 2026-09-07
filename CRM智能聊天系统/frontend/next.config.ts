import type { NextConfig } from "next";

const internalApiBaseUrl = process.env.INTERNAL_API_BASE_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/v1/:path*",
        destination: `${internalApiBaseUrl}/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
