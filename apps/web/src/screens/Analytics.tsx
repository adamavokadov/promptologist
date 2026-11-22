import { t } from '../strings.ru.ts';
import { useApp } from '../context.tsx';
import { Empty } from '../ui.tsx';

/** Placeholder until the analytics section lands. Makes no data requests. */
export function AnalyticsScreen() {
  const { me } = useApp();
  const restricted = !!me && !me.is_admin;
  return (
    <div className="col" style={{ gap: 'var(--space-6)' }}>
      <h1>{t.analytics.title}</h1>
      <Empty title={restricted ? t.analytics.state.restricted : t.analytics.state.coming} />
    </div>
  );
}
