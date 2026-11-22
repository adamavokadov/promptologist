import { useEffect, useId, useState } from 'react';
import { PROMPT_BODY_MAX, type PromptVersions } from '../../../../shared/src/prompt.ts';
import { get } from '../api.ts';
import { t } from '../strings.ru.ts';
import { fmtDate, Modal, Spinner } from '../ui.tsx';

export function VersionHistory({ url, current, onSelect }: { url: string; current: PromptVersions; onSelect: (body: string) => void }) {
  const [older, setOlder] = useState<PromptVersions['items']>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const items = [...current.items, ...older];
  const last = items.at(-1)?.version ?? 1;
  const loadOlder = async () => {
    setBusy(true);
    setError('');
    try {
      const data = await get<PromptVersions>(`${url}?before=${last}`);
      setOlder((previous) => [...previous, ...data.items]);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : t.common.error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <details className="result-details">
      <summary>{t.prompt.history}</summary>
      <ul className="col prompt-history">
        {items.map((item) => <li className="row spread wrap" key={item.version}>
          <span className="small tx2">{t.prompt.version} {item.version} · {fmtDate(item.created_at)}</span>
          <button className="btn sm" onClick={() => onSelect(item.body)}>{t.prompt.loadVersion}</button>
        </li>)}
      </ul>
      {error && <p className="banner err" role="alert">{error}</p>}
      {last > 1 && <button className="btn sm" disabled={busy} onClick={() => { void loadOlder(); }}>{busy && <Spinner />}{t.prompt.older}</button>}
    </details>
  );
}

export function PromptVersionEditor({ url, onSave, onClose }: {
  url: string;
  onSave: (body: string, expectedVersion: number) => Promise<void>;
  onClose: () => void;
}) {
  const fieldId = useId();
  const [current, setCurrent] = useState<PromptVersions | null>(null);
  const [body, setBody] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    void get<PromptVersions>(url).then((data) => {
      if (!live) return;
      setCurrent(data);
      setBody(data.items[0]?.body ?? '');
    }).catch((problem) => { if (live) setError(problem instanceof Error ? problem.message : t.common.error); });
    return () => { live = false; };
  }, [url]);
  const save = async () => {
    if (!current || busy) return;
    setBusy(true);
    setError('');
    try { await onSave(body, current.current_version); onClose(); }
    catch (problem) { setError(problem instanceof Error ? problem.message : t.common.error); }
    finally { setBusy(false); }
  };
  return (
    <Modal title={t.prompt.editor} wide onClose={onClose} footer={<>
      <button className="btn" disabled={busy} onClick={onClose}>{t.common.cancel}</button>
      <button className="btn primary" disabled={busy || !current || !body.trim() || body.trim() === current.items[0]?.body}
        onClick={() => { void save(); }}>{busy && <Spinner />}{t.prompt.saveVersion}</button>
    </>}>
      {error && <p className="banner err" role="alert">{error}</p>}
      {!current && !error && <Spinner />}
      {current && <>
        <div>
          <label className="label" htmlFor={fieldId}>{t.prompt.text}</label>
          <textarea id={fieldId} className="field mono" rows={10} maxLength={PROMPT_BODY_MAX} value={body} onChange={(event) => setBody(event.target.value)} />
        </div>
        <VersionHistory url={url} current={current} onSelect={setBody} />
      </>}
    </Modal>
  );
}
