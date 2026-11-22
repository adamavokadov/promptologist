import { useId } from 'react';
import { OPT_LIMITS } from '../../../../shared/src/optimizer.ts';
import { promptChecklist } from '../../../../shared/src/prompt.ts';
import { t } from '../strings.ru.ts';

export function PromptFields({ names, values, onChange, onCommit }: {
  names: string[];
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
  onCommit?: () => void;
}) {
  const prefix = useId();
  if (!names.length) return null;
  return (
    <fieldset className="col prompt-fields">
      <legend className="label">{t.prompt.fields}</legend>
      <div className="form-grid">{names.map((name, index) => {
        const id = `${prefix}-${index}`;
        return <div key={name}>
          <label className="label" htmlFor={id}>{name.replaceAll('_', ' ')}</label>
          <textarea id={id} rows={2} className="field" maxLength={OPT_LIMITS.variableValue}
            value={Object.hasOwn(values, name) ? values[name] : ''} onChange={(event) => onChange(name, event.target.value)} onBlur={onCommit} />
        </div>;
      })}</div>
    </fieldset>
  );
}

export function PromptChecklist({ text }: { text: string }) {
  const criteria = promptChecklist(text);
  const count = criteria.filter(({ present }) => present).length;
  const summary = count === criteria.length ? t.prompt.checklistReady : t.prompt.checklistCount.replace('{count}', String(count));
  return (
    <details className="result-details prompt-checklist">
      <summary>{summary}</summary>
      <ul className="criterion-list">
        {criteria.map(({ id, present }) => (
          <li key={id} className="row spread">
            <span>{t.prompt.criteria[id]}</span><span className={`badge ${present ? 'ok' : ''}`}>{present ? t.prompt.present : t.prompt.absent}</span>
          </li>
        ))}
      </ul>
      <p className="small tx3">{t.prompt.checklistHint}</p>
    </details>
  );
}
