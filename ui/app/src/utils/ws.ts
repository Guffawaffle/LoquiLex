export function getWsBasePath(): string {
  const envPath = (import.meta as any)?.env?.VITE_WS_PATH;
  return typeof envPath === 'string' && envPath.trim() ? envPath : '/ws';
}

export function buildWsUrl(sessionId: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const basePath = getWsBasePath();
  const path = basePath.endsWith('/') ? `${basePath}${sessionId}` : `${basePath}/${sessionId}`;
  return `${protocol}//${window.location.host}${path}`;
}
