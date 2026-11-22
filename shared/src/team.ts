import { z } from 'zod';
import { PROMPT_BODY_MAX } from './prompt.ts';

export const TEAM_ACCESS = ['reader', 'editor'] as const;
export const TEAM_VISIBILITY = ['portal', 'restricted'] as const;
export const teamFolderInput = z.object({
  name: z.string().trim().min(1).max(60),
  visibility: z.enum(TEAM_VISIBILITY),
  members: z.array(z.object({ user_id: z.string().regex(/^\d{1,18}$/), role: z.enum(TEAM_ACCESS) })).max(200),
}).refine((input) => new Set(input.members.map((member) => member.user_id)).size === input.members.length,
  { message: 'Each employee may have only one folder role', path: ['members'] });
export const teamPromptInput = z.object({
  title: z.string().trim().min(1).max(120),
  body: z.string().trim().min(1).max(PROMPT_BODY_MAX),
});
export type TeamFolderInput = z.infer<typeof teamFolderInput>;
export interface TeamFolder { id: string; name: string; visibility: TeamFolderInput['visibility']; can_edit: boolean }
export interface TeamFolders { items: TeamFolder[]; can_manage: boolean }
export interface TeamPromptSummary { id: string; title: string; preview: string; version: number; updated_at: string }
export interface TeamPrompt { id: string; title: string; body: string; version: number; updated_at: string }
