/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Optimize lucide-react imports for Next.js 15
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },
}

module.exports = nextConfig
