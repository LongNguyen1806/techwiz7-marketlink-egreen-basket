import PropTypes from 'prop-types';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '../../lib/cn';
import '../../styles/common/Button.css';

function sizeClass(size) {
    if (size === 'sm')
        return 'btn--sm';
    if (size === 'lg')
        return 'btn--lg';
    if (size === 'icon')
        return 'btn--icon';
    return 'btn--md';
}
export function Button({ className, variant = 'default', size = 'default', asChild = false, loading = false, disabled, children, ...props }) {
    const Comp = asChild ? Slot : 'button';
    const isDisabled = Boolean(disabled || loading);
    return (<Comp className={cn('btn', `btn--${variant}`, sizeClass(size), loading && 'is-loading', isDisabled && 'is-disabled', className)} disabled={isDisabled} {...props}>
      {loading ? (<>
          <span className="btn__spinner" aria-hidden="true"/>
          {children}
        </>) : (children)}
    </Comp>);
}

Button.propTypes = {
    className: PropTypes.string,
    variant: PropTypes.oneOf([
        'default',
        'secondary',
        'outline',
        'ghost',
        'accent',
        'destructive',
        'link',
    ]),
    size: PropTypes.oneOf(['default', 'sm', 'lg', 'icon']),
    asChild: PropTypes.bool,
    loading: PropTypes.bool,
    disabled: PropTypes.bool,
    children: PropTypes.node,
};

