import PropTypes from 'prop-types';
import { StatusBadge } from '../../common/StatusBadge';
import { formatDateTime } from '../../../utils/formatters';
import './OrderTimeline.css';


const ACTOR_LABEL = { CUSTOMER: 'You', FARMER: null, ADMIN: 'System', SYSTEM: 'System' };

function actorText(entry) {
  if (entry.actor_role === 'FARMER') return entry.actor_name ?? 'The farmer';
  if (entry.actor_role === 'CUSTOMER') return 'You';
  return ACTOR_LABEL[entry.actor_role] ?? 'System';
}


export function OrderTimeline({ entries }) {
  return (
    <ol className="order-timeline" aria-label="Order history">
      {entries.map((entry, index) => (
        <li className="order-timeline__step" key={`${entry.to_status}-${entry.created_at}-${index}`}>
          <span className="order-timeline__dot" aria-hidden />
          <div className="order-timeline__body">
            <div className="order-timeline__head">
              <StatusBadge status={entry.to_status} />
              <span className="order-timeline__actor">{actorText(entry)}</span>
            </div>
            <time className="order-timeline__time" dateTime={entry.created_at}>
              {formatDateTime(entry.created_at)}
            </time>
            {entry.change_reason ? (
              <p className="order-timeline__reason">{entry.change_reason}</p>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

OrderTimeline.propTypes = {
  entries: PropTypes.array.isRequired,
};
