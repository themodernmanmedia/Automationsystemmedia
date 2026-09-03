/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The dashboard never talks to platform APIs directly; everything goes
  // through our API so credentials stay server-side.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_BASE_URL ?? 'http://localhost:4000'}/api/:path*`,
      },
    ];
  },
};
export default nextConfig;
