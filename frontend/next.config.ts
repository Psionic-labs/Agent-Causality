import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // Stable build ID: repeated builds must produce the same vendored asset
  // paths, otherwise scripts/sync-explorer-static.py --check fails every time.
  generateBuildId: () => "explorer",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8766/api/:path*" },
    ];
  },
};

export default nextConfig;
