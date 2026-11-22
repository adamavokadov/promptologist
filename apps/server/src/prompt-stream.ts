import type { FastifyReply, FastifyRequest } from 'fastify';
import { AppError, log } from './util.ts';
import { VibeError } from './vibe.ts';

/** Slow LLM calls send an early event and heartbeats for the Bitrix24 Gateway. */
export async function withPromptStream<T>(req: FastifyRequest, reply: FastifyReply, run: () => Promise<T>): Promise<T | void> {
  if (!req.headers.accept?.includes('text/event-stream')) return run();
  reply.hijack();
  const stream = reply.raw;
  stream.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-store, no-transform',
    'X-Accel-Buffering': 'no',
    'X-Content-Type-Options': 'nosniff',
  });
  const send = (event: string, payload: unknown) => {
    if (!stream.destroyed && !stream.writableEnded) stream.write(`event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`);
  };
  send('working', {});
  const heartbeat = setInterval(() => { send('working', {}); }, 8_000);
  stream.once('close', () => clearInterval(heartbeat));
  try {
    send('result', await run());
  } catch (error) {
    if (error instanceof AppError) {
      send('failure', { status: error.status, code: error.code, message: error.message, retryAfter: error.retryAfter });
    } else if (error instanceof VibeError) {
      const quota = error.kind === 'quota';
      send('failure', { status: quota ? 402 : 502, code: quota ? 'ai_quota_exhausted' : 'upstream_error',
        message: quota ? 'Квота ИИ исчерпана' : 'Сервис ИИ временно недоступен', retryAfter: error.retryAfter });
    } else {
      log.error('prompt stream failed', { requestId: req.id });
      send('failure', { status: 500, code: 'internal_error', message: 'Внутренняя ошибка сервера' });
    }
  } finally {
    clearInterval(heartbeat);
    if (!stream.destroyed && !stream.writableEnded) stream.end();
  }
}
