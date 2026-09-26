import PropTypes from 'prop-types';
import { cn } from '../../lib/cn';
import '../../styles/common/StatusBadge.css';
const STATUS_META = {
    PLACED: { label: 'Placed', modifier: 'status-badge--placed' },
    ACCEPTED: { label: 'Accepted', modifier: 'status-badge--accepted' },
    READY_FOR_PICKUP: { label: 'Ready for pickup', modifier: 'status-badge--ready' },
    COMPLETED: { label: 'Completed', modifier: 'status-badge--completed' },
    DECLINED: { label: 'Declined', modifier: 'status-badge--declined' },
    CANCELLED: { label: 'Cancelled', modifier: 'status-badge--cancelled' },
    EXPIRED: { label: 'Expired', modifier: 'status-badge--expired' },
    NO_SHOW: { label: 'No-show', modifier: 'status-badge--noshow' },
};
export function StatusBadge({ status, className, }) {
    const meta = STATUS_META[status];
    return (<span className={cn('status-badge', meta.modifier, className)}>{meta.label}</span>);
}

StatusBadge.propTypes = {
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
    className: PropTypes.string,
};

