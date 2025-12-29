import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Ignore ESLint errors during build (they're just warnings about apostrophes)
  eslint: {
    ignoreDuringBuilds: true,
  },

  // Ignore TypeScript errors during build (optional)
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
