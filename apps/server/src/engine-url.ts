import { BlockList, isIP } from 'node:net';
import { lookup } from 'node:dns/promises';
import { request as httpsRequest } from 'node:https';
import { config } from './config.ts';
import { AppError } from './util.ts';

const reserved = new BlockList();
const reservedV4 = [
  ['0.0.0.0', 8], ['10.0.0.0', 8], ['100.64.0.0', 10], ['127.0.0.0', 8],
  ['169.254.0.0', 16], ['172.16.0.0', 12], ['192.0.0.0', 24], ['192.0.2.0', 24],
  ['192.168.0.0', 16], ['198.18.0.0', 15], ['198.51.100.0', 24], ['203.0.113.0', 24], ['224.0.0.0', 3],
] as const;
for (const [address, bits] of reservedV4) reserved.addSubnet(address, bits, 'ipv4');
const globalV6 = new BlockList();
globalV6.addSubnet('2000::', 3, 'ipv6');
for (const [address, bits] of [['2001::', 23], ['2001:db8::', 32], ['2002::', 16], ['3fff::', 20]] as const) {
  reserved.addSubnet(address, bits, 'ipv6');
}

function isPublic(address: string, family: number): boolean {
  if (family === 4) return !reserved.check(address, 'ipv4');
  return family === 6 && globalV6.check(address, 'ipv6') && !reserved.check(address, 'ipv6');
}

export async function resolveEngineUrl(raw: string) {
  let url: URL;
  try { url = new URL(raw); }
  catch { throw new AppError(400, 'bad_base_url', 'Custom Base URL: некорректный адрес'); }

  const allowPrivate = config.engineAllowPrivate;
  if (url.protocol !== 'https:' && !(allowPrivate && url.protocol === 'http:')) {
    throw new AppError(400, 'bad_base_url', 'Custom Base URL должен начинаться с https://');
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new AppError(400, 'bad_base_url', 'Custom Base URL должен содержать только адрес и путь');
  }
  if (allowPrivate) return { url, addresses: [] };

  const host = url.hostname.replace(/^\[|\]$/g, '');
  const family = isIP(host);
  const addresses = family ? [{ address: host, family }] : await lookup(host, { all: true }).catch(() => []);
  if (!addresses.length || addresses.some((entry) => !isPublic(entry.address, entry.family))) {
    throw new AppError(400, 'bad_base_url', 'Custom Base URL: требуется публичный адрес');
  }
  return { url, addresses };
}

const MAX_RESPONSE_BYTES = 2_000_000;

/** This lookup runs inside the connection, so it cannot resolve an unchecked address. */
export function engineUrlFetch(base: Awaited<ReturnType<typeof resolveEngineUrl>>): typeof fetch {
  const { url, addresses } = base;
  if (!addresses.length) return fetch;
  return (input, init) => new Promise<Response>((resolve, reject) => {
    const target = new URL(String(input));
    if (target.origin !== url.origin) {
      reject(new Error('Unexpected provider origin'));
      return;
    }
    const req = httpsRequest(target, {
      method: init?.method,
      headers: init?.headers as Record<string, string>,
      signal: init?.signal ?? undefined,
      agent: false,
      // Use only the validated addresses, while retaining the URL hostname for TLS.
      lookup: (_hostname, options, callback) => {
        if (options.all) callback(null, addresses);
        else callback(null, addresses[0]!.address, addresses[0]!.family);
      },
    }, (res) => {
      const status = res.statusCode ?? 502;
      if (status >= 300 && status < 400) {
        res.destroy();
        reject(new Error('Provider redirected the request'));
        return;
      }
      const chunks: Uint8Array[] = [];
      let bytes = 0;
      res.on('error', reject);
      res.on('data', (chunk: Buffer) => {
        bytes += chunk.length;
        if (bytes > MAX_RESPONSE_BYTES) res.destroy(new Error('Provider response exceeded size limit'));
        else chunks.push(chunk);
      });
      res.on('end', () => {
        const noBody = status === 204 || status === 205;
        const retryAfter = res.headers['retry-after'];
        resolve(new Response(noBody ? null : Buffer.concat(chunks), {
          status,
          headers: retryAfter ? { 'retry-after': retryAfter } : {},
        }));
      });
    });
    req.on('error', reject);
    req.end(init?.body as string | undefined);
  });
}
