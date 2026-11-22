import { useState } from 'react';
import { ExternalLink, Play } from 'lucide-react';
import { EXECUTION_MAX, type PromptExecution } from '../../../../shared/src/prompt.ts';
import { postPrompt } from '../api.ts';
import { t } from '../strings.ru.ts';
import { CopyButton, Spinner, copyText, useToast } from '../ui.tsx';

const LINKS = {
  ChatGPT: 'https://chatgpt.com/',
  Claude: 'https://claude.ai/new',
  Qwen: 'https://chat.qwen.ai/',
} as const;

export function PromptActions({ text }: { text: string }) {
  const toast = useToast();
  const [execution, setExecution] = useState<{ prompt: string; result: PromptExecution } | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState('');
  const [fallback, setFallback] = useState<string | null>(null);
  const [copying, setCopying] = useState(false);

  const openAfterCopy = async (url: string) => {
    const copied = copyText(text);
    let tab: Window | null = null;
    try {
      tab = window.open('about:blank', '_blank');
      if (tab) tab.opener = null;
    } catch {
      tab?.close();
      tab = null;
    }
    setCopying(true);
    setFallback(null);
    try {
      if (!await copied) {
        tab?.close();
        toast(t.prompt.clipboardError, 'err');
        return;
      }
      if (tab && !tab.closed) {
        try { tab.location.replace(url); }
        catch { tab.close(); setFallback(url); }
      } else {
        setFallback(url);
      }
      toast(t.common.copied, 'ok');
    } finally {
      setCopying(false);
    }
  };

  const execute = async () => {
    setBusy(true);
    setProblem('');
    setExecution(null);
    try {
      const result = await postPrompt<PromptExecution>('/api/prompts/execute', { prompt: text });
      setExecution({ prompt: text, result });
    } catch (error) {
      setProblem(error instanceof Error ? error.message : t.common.error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="col prompt-actions">
      <div className="row wrap"><CopyButton text={text} primary /></div>
      <details className="result-details">
        <summary>{t.prompt.otherActions}</summary>
        <div className="col">
          <div className="row wrap">
            {Object.entries(LINKS).map(([name, url]) => (
              <button key={name} className="btn sm" disabled={copying} onClick={() => { void openAfterCopy(url); }}>
                <ExternalLink size={14} aria-hidden />{t.prompt.copyOpen.replace('{name}', name)}
              </button>
            ))}
            {fallback && <a className="btn sm" href={fallback} target="_blank" rel="noopener noreferrer">{t.prompt.openLink}</a>}
          </div>
          <div className="row wrap">
            <button className="btn" disabled={busy || !text.trim() || text.length > EXECUTION_MAX} onClick={() => { void execute(); }}>
              {busy ? <Spinner /> : <Play size={14} aria-hidden />}{busy ? t.prompt.executing : t.prompt.execute}
            </button>
            <span className="small tx3">{text.length > EXECUTION_MAX ? t.prompt.tooLong : t.prompt.executionHint}</span>
          </div>
          {problem && <p className="banner err" role="alert">{problem}</p>}
          {execution?.prompt === text && <div className="col" aria-live="polite">
            <div className="row wrap spread"><h3>{t.prompt.answer}</h3><span className="small tx3">{execution.result.model}</span></div>
            <div className="prompt-box" tabIndex={0}>{execution.result.text}</div>
            <div className="row"><CopyButton text={execution.result.text} /></div>
          </div>}
        </div>
      </details>
    </div>
  );
}
