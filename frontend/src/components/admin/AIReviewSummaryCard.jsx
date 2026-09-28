import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { formatDateTime } from '@/utils/formatters';
import { useAIReviewStats } from '../../hooks/queries/admin/useAdminAIReview';

import './AIReviewSummaryCard.css';

const PERIODS = [7, 30, 90];

function percent(rate) {
  return rate === null || rate === undefined ? '—' : `${Math.round(rate * 100)}%`;
}

export function AIReviewSummaryCard() {
  const [days, setDays] = useState(30);
  const query = useAIReviewStats(days);
  const stats = query.data;

  return (
    <Card className="ai-summary">
      <CardHeader className="ai-summary__head">
        <CardTitle className="ai-summary__title">
          <Sparkles aria-hidden className="ai-summary__icon" />
          AI listing review
        </CardTitle>
        <div className="ai-summary__periods" role="group" aria-label="Period">
          {PERIODS.map((period) => (
            <button
              key={period}
              type="button"
              className={period === days ? 'ai-summary__period is-active' : 'ai-summary__period'}
              aria-pressed={period === days}
              onClick={() => setDays(period)}
            >
              {period} days
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {!stats ? (
          <p className="page-primitive__muted-sm">{query.isError ? 'The figures could not be loaded.' : 'Loading…'}</p>
        ) : (
          <>
            <div className="ai-summary__grid" aria-busy={query.isFetching}>
              <div className="ai-summary__stat">
                <span className="ai-summary__value">{stats.reviewed}</span>
                <span className="ai-summary__label">listings reviewed</span>
              </div>
              <div className="ai-summary__stat">
                <span className="ai-summary__value">{percent(stats.agreement_rate)}</span>
                <span className="ai-summary__label">admins agreed with its clear calls</span>
              </div>
              <div className="ai-summary__stat">
                <span className="ai-summary__value ai-summary__value--good">{stats.caught}</span>
                <span className="ai-summary__label">violations caught</span>
              </div>
              <div className="ai-summary__stat">
                <span className="ai-summary__value ai-summary__value--warn">{stats.false_alarms}</span>
                <span className="ai-summary__label">false alarms</span>
              </div>
              <div className="ai-summary__stat">
                <span className="ai-summary__value ai-summary__value--bad">{stats.missed}</span>
                <span className="ai-summary__label">missed (passed, then refused)</span>
              </div>
              <Link to="/admin/approvals" className="ai-summary__stat ai-summary__stat--link">
                <span className="ai-summary__value">{stats.open_ai_flags}</span>
                <span className="ai-summary__label">open AI flags</span>
              </Link>
            </div>
            <p className="ai-summary__foot">
              {stats.by_verdict.LIKELY_VIOLATION} likely violations · {stats.by_verdict.NEEDS_REVIEW} worth a look ·{' '}
              {stats.by_verdict.PASS} passed · {stats.ai_unavailable} with the AI unavailable ·{' '}
              {stats.last_photo_check_at
                ? `last weekly photo check ${formatDateTime(stats.last_photo_check_at)}`
                : 'no weekly photo check yet'}
              {' · '}
              <Link to="/admin/price-guidelines" className="page-primitive__link-underline">
                Price guidelines
              </Link>
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
