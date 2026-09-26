import PropTypes from 'prop-types';
import { cn } from '../../lib/cn';
import '../../styles/common/Badge.css';

export function Badge({ className, variant = 'default', ...props }) {
    return <div className={cn('badge', `badge--${variant}`, className)} {...props}/>;
}

Badge.propTypes = {
    className: PropTypes.string,
    variant: PropTypes.oneOf([
        'default',
        'secondary',
        'accent',
        'success',
        'warning',
        'danger',
        'outline',
    ]),
    children: PropTypes.node,
};

