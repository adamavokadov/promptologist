import { useMemo, useState } from 'react';
import { diffWordsWithSpace } from 'diff';
import { Minimize2 } from 'lucide-react';
import { estimateTokens, fillPromptVariables, type FolderDTO, type OptimizationDTO } from '../../../../shared/src/index.ts';
import { t } from '../strings.ru.ts';
import { patch, postPrompt, put } from '../api.ts';
import { Seg, Spinner, StarButton, useToast } from '../ui.tsx';
import { PromptActions } from './PromptActions.tsx';
import { PromptChecklist, PromptFields } from './PromptFields.tsx';
import { PromptVersionEditor } from './PromptVersionEditor.tsx';
import { PublishPrompt } from './PublishPrompt.tsx';

type Compressed = OptimizationDTO & { no_gain: boolean; saved_pct: number };
type View = 'original' | 'compressed' | 'diff';

function PromptDiff({ original, compressed }: { original: string; compressed: string }) {
  const parts = useMemo(() => diffWordsWithSpace(original, compressed, { timeout: 150 }), [original, compressed]);
  return (
    <div className="col">
      <p className="small tx2">{t.prompt.diffHint}</p>
      <div className="prompt-box prompt-diff" tabIndex={0} aria-label={t.prompt.showDiff}>
        {!parts ? <><strong>{t.opt.showOriginal}</strong>{'\n'}<del>{original}</del>{'\n\n'}
          <strong>{t.opt.showCompressed}</strong>{'\n'}<ins>{compressed}</ins></> : parts.map((part, index) =>
          part.removed ? <del key={index}>{part.value}</del> : part.added ? <ins key={index}>{part.value}</ins> : <span key={index}>{part.value}</span>)}
      </div>
    </div>
  );
}

export function OptimizationView({ item, folders, onChange }: { item: OptimizationDTO; folders: FolderDTO[]; onChange: (i: OptimizationDTO) => void }) {
  const toast = useToast();
  const [values, setValues] = useState<Record<string, string>>(item.var_values);
  const [tags, setTags] = useState(item.tags.join(', '));
  const [view, setView] = useState<View>(item.compressed_prompt ? 'compressed' : 'original');
  const [compressing, setCompressing] = useState(false);
  const [note, setNote] = useState('');
  const [editor, setEditor] = useState<'versions' | 'publish' | null>(null);
  const [savedValues, setSavedValues] = useState(item.var_values);
  const valuesDirty = values !== savedValues;
  const [saving, setSaving] = useState(false);
  const url = `/api/optimizer/items/${item.id}`;
  const original = fillPromptVariables(item.final_prompt, values);
  const compressed = item.compressed_prompt ? fillPromptVariables(item.compressed_prompt, values) : '';
  const prompt = view === 'compressed' && compressed ? compressed : original;
  const fail = (error: unknown) => toast(error instanceof Error ? error.message : t.common.error, 'err');

  const save = async (body: Record<string, unknown>) => {
    if (saving || compressing) return false;
    setSaving(true);
    try { onChange(await patch<OptimizationDTO>(url, body)); return true; }
    catch (error) { fail(error); return false; }
    finally { setSaving(false); }
  };
  const saveValues = async () => {
    if (await save({ var_values: values })) setSavedValues(values);
  };
  const compress = async () => {
    setCompressing(true);
    setNote('');
    try {
      const result = await postPrompt<Compressed>(`${url}/compress`);
      onChange(result);
      setNote(result.no_gain ? t.opt.noGain : t.opt.compressed.replace('{a}', String(result.tokens_before)).replace('{b}', String(result.tokens_after)).replace('{p}', String(result.saved_pct)));
      if (!result.no_gain) setView('compressed');
    } catch (error) { fail(error); }
    finally { setCompressing(false); }
  };
  const saveTags = () => {
    const list = tags.split(',').map((tag) => tag.trim()).filter(Boolean).slice(0, 8);
    if (JSON.stringify(list) !== JSON.stringify(item.tags)) void save({ tags: list });
  };

  return (
    <section className="surface card col prompt-result" aria-label={t.opt.finalPrompt}>
      <div className="row spread wrap"><h2>{t.opt.finalPrompt}</h2>
        <StarButton on={item.is_favorite} onClick={() => { void save({ is_favorite: !item.is_favorite }); }} />
      </div>
      <PromptFields names={item.variables} values={values} onChange={(name, value) => {
        setValues((current) => ({ ...current, [name]: value }));
      }} />
      {valuesDirty && <button className="btn sm prompt-start" disabled={saving || compressing} onClick={() => { void saveValues(); }}>{t.prompt.saveValues}</button>}
      {item.compressed_prompt && <div className="row wrap">
        <Seg label={t.opt.finalPrompt} value={view} onChange={setView} options={[
          { value: 'original', label: t.opt.showOriginal },
          { value: 'compressed', label: t.opt.showCompressed },
          { value: 'diff', label: t.prompt.showDiff },
        ]} />
      </div>}
      {view === 'diff' && item.compressed_prompt ? <>
        <PromptDiff original={item.final_prompt} compressed={item.compressed_prompt} />
        <p className="small tx3">{t.prompt.copyOutsideDiff}</p>
      </> : <>
        <div className="prompt-box" tabIndex={0} aria-label={t.opt.finalPrompt}>{prompt}</div>
        <PromptActions text={prompt} />
      </>}
      <PromptChecklist text={view === 'diff' ? compressed : prompt} />
      <details className="result-details">
        <summary>{t.prompt.details}</summary>
        <div className="col">
          <div className="row wrap">
            <button className="btn" onClick={() => { void compress(); }} disabled={compressing || saving}>
              {compressing ? <Spinner /> : <Minimize2 size={15} aria-hidden />}{compressing ? t.opt.compressing : t.opt.compress}
            </button>
            <span className="small tx3 mono">{t.prompt.tokenCount.replace('{count}', String(estimateTokens(view === 'diff' ? compressed : prompt)))}</span>
          </div>
          {note && <p className="small tx2" role="status">{note}</p>}
          {item.initial_critique && <p className="small tx2">{item.initial_critique}</p>}
          {item.changelog_explanation.length > 0 && <div className="col">
            <h3>{t.opt.changelog}</h3><ul className="prompt-explanations">{item.changelog_explanation.map((item, i) => <li key={i}>{item}</li>)}</ul>
          </div>}
          <div className="form-grid">
            <div><label className="label" htmlFor={`folder-${item.id}`}>{t.opt.folder}</label>
              <select id={`folder-${item.id}`} className="field" disabled={saving || compressing} value={item.folder_id ?? ''}
                onChange={(event) => { void save({ folder_id: event.target.value || null }); }}>
                <option value="">{t.opt.noFolder}</option>{folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
              </select>
            </div>
            <div><label className="label" htmlFor={`tags-${item.id}`}>{t.opt.tags}</label>
              <input id={`tags-${item.id}`} className="field" value={tags} disabled={saving || compressing} onChange={(event) => setTags(event.target.value)} onBlur={saveTags} />
            </div>
          </div>
          <div className="row wrap">
            <button className="btn sm" disabled={saving || compressing} onClick={() => setEditor('versions')}>{t.prompt.editVersion}</button>
            <button className="btn sm" disabled={saving || compressing} onClick={() => setEditor('publish')}>{t.team.publish}</button>
          </div>
          {item.model && <p className="small tx3">{t.opt.engine} · <span className="mono">{item.model}</span></p>}
        </div>
      </details>
      {editor === 'versions' && <PromptVersionEditor url={`${url}/versions`} onClose={() => setEditor(null)} onSave={async (body, expected_version) => {
        onChange(await put<OptimizationDTO>(`${url}/prompt`, { body, expected_version }));
        setNote('');
        setView('original');
      }} />}
      {editor === 'publish' && <PublishPrompt body={item.final_prompt} onClose={() => setEditor(null)} />}
    </section>
  );
}
