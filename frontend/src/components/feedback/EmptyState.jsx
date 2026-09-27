import PropTypes from 'prop-types';
import { Inbox } from 'lucide-react';
import { Button } from '../ui/Button';
import { cn } from '../../lib/cn';
import '../../styles/common/EmptyState.css';
export function EmptyState({ title, description, actionLabel, onAction, icon, className, }) {
    return (<div className={cn('empty-state', className)}>
      <div className="empty-state__icon-wrap">
        {icon ?? <Inbox className="empty-state__icon" aria-hidden/>}
      </div>
      <h3 className="empty-state__title">{title}</h3>
      {description ? <p className="empty-state__description">{description}</p> : null}
      {actionLabel && onAction ? (<Button className="empty-state__action" onClick={onAction}>
          {actionLabel}
        </Button>) : null}
    </div>);
}

EmptyState.propTypes = {
    title: PropTypes.string.isRequired,
    description: PropTypes.string,
    actionLabel: PropTypes.string,
    onAction: PropTypes.func,
    icon: PropTypes.node,
    className: PropTypes.string,
};

