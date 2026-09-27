import PropTypes from 'prop-types';
import { cn } from '../../lib/cn';
import '../../styles/common/Skeleton.css';
export function Skeleton({ className, ...props }) {
    return <div className={cn('skeleton', className)} {...props}/>;
}

Skeleton.propTypes = {
    className: PropTypes.string,
};

