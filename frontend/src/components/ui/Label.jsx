import PropTypes from 'prop-types';
import * as LabelPrimitive from '@radix-ui/react-label';
import { cn } from '../../lib/cn';
import '../../styles/common/Label.css';
export function Label({ className, ...props }) {
    return <LabelPrimitive.Root className={cn('label', className)} {...props}/>;
}

Label.propTypes = {
    className: PropTypes.string,
    children: PropTypes.node,
};

