import { useId, useState, type Dispatch, type SetStateAction } from 'react';
import { OPT_LIMITS } from '../../../../shared/src/optimizer.ts';
import { postPrompt } from '../api.ts';
import { t } from '../strings.ru.ts';
import { Spinner } from '../ui.tsx';

export function ClarificationForm({ questions, answers, setAnswers, suggestUrl, busy, onContinue, onSkip }: {
  questions: string[];
  answers: string[];
  setAnswers: Dispatch<SetStateAction<string[]>>;
  suggestUrl: string;
  busy: boolean;
  onContinue: () => void;
  onSkip?: () => void;
}) {
  const prefix = useId();
  const [suggesting, setSuggesting] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [error, setError] = useState('');
  async function suggest() {
    setSuggesting(true);
    setError('');
    try {
      const reply = await postPrompt<{ answers: string[] }>(suggestUrl);
      setAnswers((current) => questions.map((_, index) => current[index]?.trim() ? current[index]! : reply.answers[index] ?? ''));
      setGenerated(true);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : t.common.error);
    } finally {
      setSuggesting(false);
    }
  }
  return (
    <section className="surface card col" aria-labelledby={`${prefix}-heading`}>
      <h2 id={`${prefix}-heading`}>{t.opt.questionsTitle}</h2>
      {questions.map((question, index) => {
        const id = `${prefix}-${index}`;
        return <div key={id}>
          <label className="label" htmlFor={id}>{question}</label>
          <textarea id={id} className="field" rows={2} maxLength={OPT_LIMITS.answerMax} value={answers[index] ?? ''}
            onChange={(event) => setAnswers(questions.map((_, j) => j === index ? event.target.value : answers[j] ?? ''))} />
        </div>;
      })}
      {generated && <p className="small tx2" role="status">{t.prompt.suggestionsHint}</p>}
      {error && <p className="banner err" role="alert">{error}</p>}
      <div className="row wrap">
        <button className="btn primary" disabled={busy || suggesting} onClick={onContinue}>{busy && <Spinner />}{t.opt.answerContinue}</button>
        <button className="btn" disabled={busy || suggesting || !questions.some((_, i) => !answers[i]?.trim())} onClick={() => { void suggest(); }}>
          {suggesting && <Spinner />}{t.prompt.suggestAnswers}
        </button>
        {onSkip && <button className="btn sm ghost" disabled={busy || suggesting} onClick={onSkip}>{t.opt.answerSkip}</button>}
      </div>
    </section>
  );
}
