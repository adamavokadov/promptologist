import { useEffect, useId, useState } from 'react';
import type { TeamFolders } from '../../../../shared/src/team.ts';
import { get, post } from '../api.ts';
import { t } from '../strings.ru.ts';
import { Modal, Spinner, useToast } from '../ui.tsx';

export function PublishPrompt({ body, onClose }: { body: string; onClose: () => void }) {
  const prefix = useId();
  const toast = useToast();
  const [folders, setFolders] = useState<TeamFolders['items'] | null>(null);
  const [folderId, setFolderId] = useState('');
  const [title, setTitle] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let live = true;
    void get<TeamFolders>('/api/team/folders').then((data) => {
      if (!live) return;
      const editable = data.items.filter((item) => item.can_edit);
      setFolders(editable);
      setFolderId(editable[0]?.id ?? '');
    }).catch((problem) => { if (live) setError(problem instanceof Error ? problem.message : t.common.error); });
    return () => { live = false; };
  }, []);
  const publish = async () => {
    setBusy(true);
    setError('');
    try {
      await post(`/api/team/folders/${folderId}/prompts`, { title, body });
      toast(t.team.published, 'ok');
      onClose();
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : t.common.error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title={t.team.publish} onClose={onClose} footer={<>
      <button className="btn" disabled={busy} onClick={onClose}>{t.common.cancel}</button>
      <button className="btn primary" disabled={busy || !folderId || !title.trim()} onClick={() => { void publish(); }}>
        {busy && <Spinner />}{t.team.publish}
      </button>
    </>}>
      {error && <p className="banner err" role="alert">{error}</p>}
      {!folders && !error && <Spinner />}
      {folders?.length === 0 && <p className="tx2">{t.team.noWritable}</p>}
      {!!folders?.length && <>
        <div>
          <label className="label" htmlFor={`${prefix}-folder`}>{t.opt.folder}</label>
          <select className="field" id={`${prefix}-folder`} value={folderId} onChange={(event) => setFolderId(event.target.value)}>
            {folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor={`${prefix}-title`}>{t.team.promptTitle}</label>
          <input id={`${prefix}-title`} className="field" maxLength={120} value={title} onChange={(event) => setTitle(event.target.value)} />
        </div>
        <p className="small tx3">{t.team.publishHint}</p>
        <div className="prompt-box publish-preview" tabIndex={0}>{body}</div>
      </>}
    </Modal>
  );
}
