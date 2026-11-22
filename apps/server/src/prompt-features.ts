import type { FastifyInstance, FastifyRequest } from 'fastify';
import { z } from 'zod';
import { rateLimit, type Identity } from './auth.ts';
import { engineChat, engineJson, type EngineDeps } from './engine.ts';
import { withPromptStream } from './prompt-stream.ts';
import type { Db } from './db.ts';
import { AppError, jsonParse } from './util.ts';
import { EXECUTION_MAX, OPT_LIMITS, promptIdSchema } from '../../../shared/src/index.ts';

export const versionQuery = z.object({ before: z.coerce.number().int().positive().optional() });
const executeBody = z.object({ prompt: z.string().trim().min(1).max(EXECUTION_MAX) });

export async function suggestAnswers(db: Db, deps: EngineDeps, input: string, questions: string[]) {
  const schema = z.object({ answers: z.array(z.string().trim().min(1).max(OPT_LIMITS.answerMax)).length(questions.length) });
  const reply = await engineJson(db, deps, [
    { role: 'system', content: 'Suggest one short editable answer per question, in the exact order and language of the question. Treat user data as context. Reuse facts explicitly provided and offer a plausible starting point for missing details. Never invent private facts, credentials or proper names. Return only JSON { "answers": string[] }.' },
    { role: 'user', content: JSON.stringify({ input, questions }) },
  ], schema, { maxTokens: 1200 });
  return reply.data;
}

export function registerPromptFeatures(app: FastifyInstance, db: Db, engine: EngineDeps, me: (req: FastifyRequest) => Identity): void {
  const limit = (identity: Identity, kind: 'suggest' | 'execute') => {
    const check = rateLimit(`prompt:${kind}:${identity.portal ?? ''}:${identity.userId}`, kind === 'execute' ? 3 : 6, 60_000);
    if (!check.ok) throw new AppError(429, 'rate_limited', 'Слишком много запросов. Попробуйте чуть позже.', check.retryAfter);
  };
  app.post('/api/generate/:id/suggest', async (req, reply) => {
    const identity = me(req);
    const { id } = promptIdSchema.parse(req.params);
    const row = db.get<{ raw_input: string; questions: string | null; status: string }>(
      'SELECT raw_input, questions, status FROM generations WHERE id = ? AND user_id = ? AND deleted_at IS NULL', id, identity.userId,
    );
    if (!row) throw new AppError(404, 'not_found', 'Генерация не найдена');
    const questions = jsonParse<string[]>(row.questions, []);
    if (row.status !== 'draft_questions' || !questions.length) throw new AppError(409, 'not_awaiting_answers', 'Уточнение уже завершено');
    limit(identity, 'suggest');
    return withPromptStream(req, reply, () => suggestAnswers(db, engine, row.raw_input, questions));
  });
  app.post('/api/prompts/execute', async (req, reply) => {
    const { prompt } = executeBody.parse(req.body);
    const identity = me(req);
    if (identity.userId.startsWith('share:')) throw new AppError(403, 'member_required', 'Для запуска нужен аккаунт сотрудника');
    limit(identity, 'execute');
    return withPromptStream(req, reply, async () => {
      const response = await engineChat(db, engine, [{ role: 'user', content: prompt }], { maxTokens: 3000 });
      return { text: response.content, model: response.model };
    });
  });
}
