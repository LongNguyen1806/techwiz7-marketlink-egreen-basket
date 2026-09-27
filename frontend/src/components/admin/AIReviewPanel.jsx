import { useState } from 'react';
import PropTypes from 'prop-types';
import { Bot, Camera, ListChecks, RefreshCw, Sparkles } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { formatDateTime } from '@/utils/formatters';
import { cn } from '@/lib/cn';

import './AIReviewPanel.css';

export const AI_VERDICT = {
  PASS: { label: 'No issues found', variant: 'success' },
  NEEDS_REVIEW: { label: 'Worth a closer look', variant: 'warning' },
  LIKELY_VIOLATION: { label: 'Likely breaks the rules', variant: 'danger' },
  UNAVAILABLE: { label: 'AI unavailable', variant: 'secondary' },
};

const SEVERITY_ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 };
const COLLAPSED_FINDINGS = 3;

function riskLevel(score) {
  if (score >= 60) return 'high';
  if (score >= 30) return 'medium';
  return 'low';
}

/** "Rules" or "AI": which layer said it, so an admin knows how much to weigh it. */
function SourceTag({ source }) {
  const isAI = source === 'ai';
  const Icon = isAI ? Bot : ListChecks;
  return (
    <span className={cn('ai-review__source', isAI && 'ai-review__source--ai')}>
      <Icon aria-hidden className="ai-review__source-icon" />
      {isAI ? 'AI' : 'Rules'}
    </span>
  );
}

SourceTag.propTypes = { source: PropTypes.string.isRequired };

/**
 * The AI's advice on one listing, next to the admin's Approve / Refuse buttons.
 *
 * Advice only: nothing here approves, refuses or hides. The admin reads it and decides.
 */
export function AIReviewPanel({ review, photoCheck, onRecheck, rechecking = false }) {
  const [expanded, setExpanded] = useState(false);

  if (!review) {
    return (
      <div className="ai-review ai-review--empty">
        <div className="ai-review__head">
          <span className="ai-review__title">
            <Sparkles aria-hidden className="ai-review__title-icon" />
            AI review
          </span>
          <Badge variant="outline">Not reviewed yet</Badge>
          {onRecheck ? (
            <Button size="sm" variant="ghost" loading={rechecking} onClick={onRecheck} className="ai-review__rerun">
              <RefreshCw aria-hidden className="ai-review__rerun-icon" />
              Run AI review
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  const verdict = AI_VERDICT[review.verdict] ?? AI_VERDICT.UNAVAILABLE;
  const findings = [...(review.findings ?? [])].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3),
  );
  const shown = expanded ? findings : findings.slice(0, COLLAPSED_FINDINGS);
  const level = riskLevel(review.risk_score);

  return (
    <section className={cn('ai-review', `ai-review--${review.verdict.toLowerCase()}`)} aria-label="AI review">
      <div className="ai-review__head">
        <span className="ai-review__title">
          <Sparkles aria-hidden className="ai-review__title-icon" />
          AI review
        </span>
        <Badge variant={verdict.variant}>{verdict.label}</Badge>
        <span className="ai-review__risk" title={`Risk ${review.risk_score} of 100`}>
          <span className="ai-review__risk-track" aria-hidden>
            <span className={cn('ai-review__risk-fill', `ai-review__risk-fill--${level}`)} style={{ width: `${review.risk_score}%` }} />
          </span>
          <span className="ai-review__risk-value">Risk {review.risk_score}</span>
        </span>
        {onRecheck ? (
          <Button size="sm" variant="ghost" loading={rechecking} onClick={onRecheck} className="ai-review__rerun">
            <RefreshCw aria-hidden className="ai-review__rerun-icon" />
            Re-run
          </Button>
        ) : null}
      </div>

      {review.summary ? <p className="ai-review__summary">{review.summary}</p> : null}

      {findings.length ? (
        <ul className="ai-review__findings">
          {shown.map((finding, index) => (
            <li key={`${finding.check}-${index}`} className="ai-review__finding">
              <span className={cn('ai-review__dot', `ai-review__dot--${finding.severity.toLowerCase()}`)} title={finding.severity} />
              <SourceTag source={finding.source} />
              <span className="ai-review__message">{finding.message}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {findings.length > COLLAPSED_FINDINGS ? (
        <button type="button" className="ai-review__more" onClick={() => setExpanded((open) => !open)}>
          {expanded ? 'Show fewer' : `Show all ${findings.length} findings`}
        </button>
      ) : null}

      {review.suggested_category ? (
        <p className="ai-review__note">
          Suggested category: <strong>{review.suggested_category.name}</strong>
        </p>
      ) : null}
      {!review.ai_used && review.ai_error ? (
        <p className="ai-review__note">AI not used: {review.ai_error}. The rule checks above still ran.</p>
      ) : null}
      {photoCheck ? (
        <p className="ai-review__note">
          <Camera aria-hidden className="ai-review__note-icon" />
          Weekly photo check: {AI_VERDICT[photoCheck.verdict]?.label ?? photoCheck.verdict} · {formatDateTime(photoCheck.created_at)}
        </p>
      ) : null}

      <p className="ai-review__footer">
        Advice only, the decision is yours · {review.ai_used ? review.model_name : 'rules only'} ·{' '}
        {formatDateTime(review.created_at)}
      </p>
    </section>
  );
}

AIReviewPanel.propTypes = {
  review: PropTypes.shape({
    verdict: PropTypes.string.isRequired,
    risk_score: PropTypes.number.isRequired,
    summary: PropTypes.string,
    findings: PropTypes.arrayOf(
      PropTypes.shape({
        source: PropTypes.string,
        check: PropTypes.string,
        severity: PropTypes.string,
        message: PropTypes.string,
      }),
    ),
    suggested_category: PropTypes.shape({ id: PropTypes.number, name: PropTypes.string }),
    ai_used: PropTypes.bool,
    ai_error: PropTypes.string,
    model_name: PropTypes.string,
    created_at: PropTypes.string,
  }),
  photoCheck: PropTypes.shape({ verdict: PropTypes.string, created_at: PropTypes.string }),
  onRecheck: PropTypes.func,
  rechecking: PropTypes.bool,
};
