# Prompt workspace v1.2

## Product decisions

The default route and the **New prompt** action open one workspace. The user submits a task, a prompt, or an idea in the same composer. The detected mode appears by the submit button. The selector allows an override, including reusable template and style extraction. The old Generator and Optimizer deep links remain available.

| Input | Default action |
| --- | --- |
| Concrete request, such as a task beginning with an imperative | Generate a prompt for one selected system through the existing skill pipeline |
| A prompt with explicit sections or other strong structural cues | Optimize it through the configured engine |
| An idea without an action, or a request with too little information for the Generator | Ask clarification questions through the Optimizer |
| A request beginning with “Помоги проверить гипотезу” | Use the Generator’s Hypothesis validation preset |

Auto mode is rule-based. It does not make a classification request or send the draft to a model before submission. The workspace uses the first configured Generator system by default and exposes the model choice in the mode panel. Prompts above the Generator’s length limit use the Optimizer in auto mode within its input limit. Distinct mode selections live under the composer. A manual Generator selection keeps existing validation and system settings.

The hypothesis preset asks for a falsifiable proposition, the audience, the cheapest credible test, the resources and timeline, measurable success and stop thresholds, and a decision rule. It states assumptions where evidence is missing. The app provides the existing prompt-generation flow for this preset.

Optional examples target Marketing, HR and Management. Each role has three illustrative before/after examples. Selecting an example fills the composer. “Answer for me” suggests one answer per existing question, fills empty fields and leaves manual answers intact. The user reviews and submits the form explicitly.

## Results and visual system

Obsidian / Linear Dark is the baseline. The unified composer uses the existing surface, controls and typography tokens. On a narrow screen, the composer and prompt text with its copy action remain primary. Mode options, examples, model commentary, token counts and secondary actions live in accordions. View choices and variable fields stay next to the prompt they affect.

The checklist flags four explicit elements in the text using labels and useful phrasing in Russian and English: role, context, constraints, and output format. It is recomputed from the displayed text, including legacy saved prompts, and reports presence without a model score or another model call. A 4/4 result means all four elements were detected by the text rules.

Compression comparison uses a word-level diff. Deletions are muted and struck through, additions are underlined. If the diff exceeds its time budget, the UI shows both texts for comparison. The number of tokens is an estimate. Copy and model execution operate on the selected original or compressed variant with the current fields filled. The diff itself is a review view.

The field form recognizes both `[Insert source text]` and `{{Имя_клиента}}` in saved prompts. Unresolved placeholders remain as written and substitution runs once. Personal fields can be saved explicitly. Values in the team reader's form are local to that open item and are never added to the shared template.

Buttons can copy a prompt and open ChatGPT, Claude or Qwen in a new tab. The browser clipboard holds the prompt. Destination URLs are fixed and contain no prompt text. If opening is blocked after the copy, a manual link appears. Native Bitrix24 mobile clients may impose additional clipboard or popup restrictions.

“Run prompt here” passes only the rendered text selected by the user to the existing configured optimizer engine. The model response is displayed as text. The endpoint has no tools, CRM calls, external browser control or automatic follow-up. Output is transient. The selected provider processes the prompt and may account for it according to its plan. The endpoint is restricted to signed-in users and limited to three launches per user per minute.

## Team library

**Library → Общие** contains portal-scoped folders. An administrator creates a folder such as **Отдел продаж**, chooses its visibility, and assigns employee IDs from Bitrix24.

| Role | See the current prompt and use it | Publish and edit | Manage folder access |
| --- | --- | --- | --- |
| Administrator | Yes, within their portal | Yes | Yes |
| Editor assigned to a folder | Yes | Yes, including its editable history and removal of shared prompts | No |
| Reader assigned to a folder | Yes | No | No |
| Other employee of the same portal | When the folder is visible to the portal | No | No |
| Other portal or guest | No | No | No |

New folders default to restricted visibility. Folder membership uses Bitrix24 employee IDs assigned in the app. CRM records and organizational department membership are not queried. The server uses the trusted Alaio Gateway portal UUID and employee identity at each team request. Deploy the origin behind that Gateway. A publication is a separate copy of the current source prompt, with placeholders and no form values. Publishing, revising or deleting that copy does not change the personal item.

## Versions and persistence

SQLite migration v3 creates `prompt_versions`, `team_folders`, `team_folder_members` and `team_prompts`. Existing personal content stays in its original table. The first text edit snapshots the previous content as version 1. Future edits append a revision. Restoring an older body uses the same save path and creates another revision. Versions cover personal Optimizer results, editable personal templates, and shared prompt bodies. The Generator's generated variants retain their existing history. Store a generated result as a personal template to start editing its text manually.

Writes use the current version as a conflict check for the editor, and personal text edits atomically clear any outdated compression and refresh the index. Deleting a prompt also removes its revision entries. Saved variable values, tags and favourites belong to the personal item and are not counted as text revisions.

## HTTP and release checks

- `POST /api/optimizer/items/:id/suggest`, `POST /api/generate/:id/suggest` suggest answers to the caller's draft.
- `POST /api/prompts/execute` runs a single text prompt using the configured engine.
- `GET /api/optimizer/items/:id/versions` and `PUT /api/optimizer/items/:id/prompt` support optimistic edits. Personal templates expose `GET /api/templates/:id/versions` and use their existing PATCH route to save.
- `/api/team/folders` contains folder management and `/api/team/folders/:folderId/prompts` contains the prompt records and revisions.
- Model requests from the browser use Server-Sent Events with an initial progress event and periodic heartbeats. The JSON interface is retained for existing clients. The Gateway sets a short deadline for ordinary HTTP responses while models can take longer.
- Before deploying, back up the SQLite volume. On the actual Bitrix24 portal, verify administrator/editor/reader and guest roles, copy/open behavior inside the mobile iframe and one real engine call covering generation, optimization and execution. Review portal ACL and provider quota before wider rollout.

References

- [Alaio Gateway identity, headers and timeouts](https://vibecode.bitrix24.com/docs/infra/app-runtime)
- [Qwen web chat](https://chat.qwen.ai/)
- [Claude browser access](https://support.claude.com/en/articles/8114491-get-started-with-claude)
