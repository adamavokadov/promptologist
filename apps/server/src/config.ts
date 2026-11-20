import fs from 'node:fs';
import path from 'node:path';

function resolveDataDir(): string {
  if (process.env.DATA_DIR) return process.env.DATA_DIR;
  for (const candidate of ['/data', '/opt/app/data']) {
    try {
      fs.mkdirSync(candidate, { recursive: true });
      fs.accessSync(candidate, fs.constants.W_OK);
      return candidate;
    } catch { /* try next */ }
  }
  return path.resolve(process.cwd(), 'data');
}

export const config = {
  port: Number(process.env.PORT ?? 3000),
  nodeEnv: process.env.NODE_ENV ?? 'development',
  /** Service key (vibe_api_...) for AI router, search, infra, notifications and background jobs. */
  apiKey: process.env.VIBE_API_KEY ?? '',
  /** OAuth application key (vibe_app_...) used together with the forwarded session to resolve identity via GET /v1/me. */
  appKey: process.env.VIBE_APP_KEY ?? '',
  baseUrl: (process.env.VIBE_BASE_URL ?? 'https://vibecode.bitrix24.com/v1').replace(/\/+$/, ''),
  serverId: process.env.VIBE_SERVER_ID ?? '',
  publicUrl: (process.env.APP_PUBLIC_URL ?? '').replace(/\/+$/, ''),
  dataDir: resolveDataDir(),
  jobSecret: process.env.JOB_SECRET ?? '',
  jobSecretPrevious: process.env.JOB_SECRET_PREVIOUS ?? '',
  /** Local development only: skip Gateway identity (ignored when NODE_ENV=production). */
  devAuthBypass: process.env.DEV_AUTH_BYPASS === '1' && (process.env.NODE_ENV ?? 'development') !== 'production',
  staticDir: process.env.STATIC_DIR ?? path.resolve(process.cwd(), 'dist/public'),
};
export type Config = typeof config;

export function maskSecrets(text: string): string {
  return text
    .replace(/vibe_(api|app|session)_[A-Za-z0-9_-]{6,}/g, 'vibe_$1_***')
    .replace(/vjs_[A-Za-z0-9_-]{10,}/g, 'vjs_***')
    .replace(/t=\d+,v1=[0-9a-f]{64}/g, 't=***,v1=***');
}
