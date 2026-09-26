import * as React from 'react';
import PropTypes from 'prop-types';
import { cn } from '../../lib/cn';
import '../../styles/common/Textarea.css';
export const Textarea = React.forwardRef(({ className, ...props }, ref) => {
    return <textarea className={cn('textarea', className)} ref={ref} {...props}/>;
});
Textarea.displayName = 'Textarea';

Textarea.propTypes = {
    className: PropTypes.string,
};

