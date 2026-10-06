import type { NextConfig } from "next";

// Static export: Vercel serves plain files and the browser calls the Lambda API directly (spec 0001).
const nextConfig: NextConfig = {
  output: "export",
};

export default nextConfig;
