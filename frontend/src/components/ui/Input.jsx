import * as React from 'react';
import PropTypes from 'prop-types';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '../../lib/cn';
import '../../styles/common/Input.css';

export const Input = React.forwardRef(({ className, type, id, label, placeholder, disabled, requiredMark, ...props }, ref) => {
    const generatedId = React.useId();
    const inputId = id ?? generatedId;
    const floatingLabel = label ?? placeholder;
    const useFloating = Boolean(floatingLabel) && type !== 'file';
    const isPassword = type === 'password';
    const [passwordVisible, setPasswordVisible] = React.useState(false);
    const inputType = isPassword && passwordVisible ? 'text' : type;
    const toggleButton = isPassword ? (<button type="button" className="input-field__toggle" aria-label={passwordVisible ? 'Hide password' : 'Show password'} aria-pressed={passwordVisible} disabled={disabled} onClick={() => {
            setPasswordVisible((current) => !current);
        }}>
        {passwordVisible ? (<EyeOff className="input-field__toggle-icon" strokeWidth={1.75} aria-hidden/>) : (<Eye className="input-field__toggle-icon" strokeWidth={1.75} aria-hidden/>)}
      </button>) : null;
    if (!useFloating) {
        if (!isPassword) {
            return (<input id={id} type={type} className={cn('input', className)} placeholder={placeholder} disabled={disabled} ref={ref} {...props}/>);
        }
        return (<div className={cn('input-field', 'input-field--password', className)}>
          <input id={id} type={inputType} className="input input--password" placeholder={placeholder} disabled={disabled} ref={ref} {...props}/>
          {toggleButton}
        </div>);
    }
    return (<div className={cn('input-field', isPassword && 'input-field--password', className)}>
        <input id={inputId} type={inputType} className={cn('input', isPassword && 'input--password')} placeholder=" " disabled={disabled} ref={ref} {...props}/>
        <label htmlFor={inputId} className="input-field__label">
          {floatingLabel}
          {requiredMark ? (
            <span className="input-field__required" aria-hidden>
              {' '}*
            </span>
          ) : null}
        </label>
        {toggleButton}
      </div>);
});
Input.displayName = 'Input';

Input.propTypes = {
    className: PropTypes.string,
    type: PropTypes.string,
    id: PropTypes.string,
    label: PropTypes.string,
    placeholder: PropTypes.string,
    disabled: PropTypes.bool,
};

