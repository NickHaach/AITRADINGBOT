/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async rewrites() {
    const market = process.env.NEXT_PUBLIC_MARKET_URL ?? "http://127.0.0.1:8002";
    return [
      {
        source: "/proxy/market/:path*",
        destination: `${market}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
