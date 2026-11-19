const config = {
  // Production settings
  reactStrictMode: true,
  swcMinify: true,
  poweredByHeader: false,

  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-XSS-Protection', value: '1; mode=block' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Content-Security-Policy', value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:; font-src 'self' data:; connect-src 'self' http://localhost:8000 https: wss:; frame-ancestors 'none';" },
        ],
      },
    ];
  },

  // Environment variables
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
  },

  // Images
  images: {
    domains: ['localhost'],
    unoptimized: process.env.NODE_ENV === 'production',
  },

  // Webpack
  webpack: (config, { dev }) => {
    // Enable source maps in production for debugging
    if (!dev) {
      config.devtool = 'source-map';
    }
    return config;
  },

  // Experimental features
  experimental: {
    serverComponentsExternalPackages: [],
  },

  // Output
  output: 'standalone',
};

export default config;