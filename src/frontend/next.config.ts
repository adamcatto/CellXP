import os from 'os';
import type { NextConfig } from 'next';

const apiProxyTarget =
  process.env.CELLXP_API_PROXY_TARGET ?? 'http://127.0.0.1:8001';

/** Hostnames/IPs that may load `/_next/*` and the HMR WebSocket in dev (not just `localhost`). */
function resolveAllowedDevOrigins(): string[] {
  const hosts = new Set<string>(['127.0.0.1']);

  for (const addrs of Object.values(os.networkInterfaces())) {
    for (const addr of addrs ?? []) {
      if (addr.family === 'IPv4' && !addr.internal) {
        hosts.add(addr.address);
      }
    }
  }

  for (const origin of process.env.CELLXP_DEV_ORIGINS?.split(',') ?? []) {
    const trimmed = origin.trim();
    if (trimmed) hosts.add(trimmed);
  }

  return [...hosts];
}

const allowedDevOrigins = resolveAllowedDevOrigins();

const nextConfig: NextConfig = {
  allowedDevOrigins,
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiProxyTarget}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
