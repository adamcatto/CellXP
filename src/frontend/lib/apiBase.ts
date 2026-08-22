const DEFAULT_API_BASE = '/api/v1';

function normalizeBase(url: string): string {
  return url.replace(/\/$/, '');
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}

function isLoopbackUrl(url: string): boolean {
  try {
    return isLoopbackHostname(new URL(url).hostname);
  } catch {
    return false;
  }
}

/** Same-origin `/api/v1` by default; host-aware fallback when env points at loopback. */
export function getApiBase(): string {
  const configured =
    typeof process !== 'undefined' ? process.env.NEXT_PUBLIC_API_BASE : undefined;

  if (configured) {
    const base = normalizeBase(configured);
    if (base.startsWith('/')) return base;
    if (typeof window === 'undefined' || !isLoopbackUrl(base)) return base;
    if (!isLoopbackHostname(window.location.hostname)) {
      const port = process.env.NEXT_PUBLIC_API_PORT ?? '8001';
      return `${window.location.protocol}//${window.location.hostname}:${port}/api/v1`;
    }
    return base;
  }

  return DEFAULT_API_BASE;
}
