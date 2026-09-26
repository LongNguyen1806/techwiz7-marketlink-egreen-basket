import PropTypes from 'prop-types';
import { Check, Circle, X } from 'lucide-react';
import { cn } from '../../lib/cn';
import '../../styles/common/OrderTimeline.css';

const MAIN_STEPS = [
  { key: 'PLACED', label: 'Placed' },
  { key: 'ACCEPTED', label: 'Accepted' },
  { key: 'READY_FOR_PICKUP', label: 'Ready' },
  { key: 'COMPLETED', label: 'Completed' },
];

const ENDINGS = {
  DECLINED: { label: 'Declined', modifier: 'order-timeline__branch--danger' },
  CANCELLED: { label: 'Cancelled', modifier: 'order-timeline__branch--danger' },
  EXPIRED: { label: 'Expired', modifier: 'order-timeline__branch--muted' },
  NO_SHOW: { label: 'No-show', modifier: 'order-timeline__branch--warning' },
};



function reachedSteps(status, history) {
  const reached = new Set(['PLACED']);
  history.forEach((entry) => reached.add(entry.to_status));
  const current = MAIN_STEPS.findIndex((step) => step.key === status);
  MAIN_STEPS.forEach((step, index) => {
    if (index <= current) reached.add(step.key);
  });
  return reached;
}

export function OrderTimeline({ status, history = [] }) {
  const ending = ENDINGS[status];
  const reached = reachedSteps(status, history);

  return (
    <div className="order-timeline">
      <ol className="order-timeline__steps">
        {MAIN_STEPS.map((step) => {
          const done = reached.has(step.key);
          return (
            <li
              key={step.key}
              className={cn(
                'order-timeline__step',
                done && 'is-done',
                step.key === status && status === 'READY_FOR_PICKUP' && 'is-pulse',
              )}
              aria-current={step.key === status ? 'step' : undefined}
            >
              <div className="order-timeline__icon-wrap">
                {done ? (
                  <Check className="order-timeline__icon is-done" />
                ) : (
                  <Circle className="order-timeline__icon is-pending" />
                )}
              </div>
              <p className="order-timeline__label">{step.label}</p>
            </li>
          );
        })}
      </ol>
      {ending ? (
        <div className={cn('order-timeline__branch', ending.modifier)}>
          <X className="order-timeline__branch-icon" />
          Ended: {ending.label}
        </div>
      ) : null}
    </div>
  );
}

OrderTimeline.propTypes = {
  status: PropTypes.oneOf([
    'PLACED',
    'ACCEPTED',
    'READY_FOR_PICKUP',
    'COMPLETED',
    'DECLINED',
    'CANCELLED',
    'EXPIRED',
    'NO_SHOW',
  ]).isRequired,
  history: PropTypes.arrayOf(PropTypes.shape({ to_status: PropTypes.string })),
};
