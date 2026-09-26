import PropTypes from 'prop-types';
import { Input } from '../../ui/Input';
import './FormField.css';

/**
 * One labelled input plus its message. The message is tied to the input with `aria-describedby`,
 * so a screen reader reads "Email — This email is already registered." instead of leaving the
 * error stranded next to the box, and every auth screen reports errors the same way.
 */
export function FormField({ id, label, error, ...field }) {
  const errorId = `${id}-error`;

  return (
    <div className="form-field">
      <Input
        id={id}
        label={label}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? errorId : undefined}
        {...field}
      />
      {error ? (
        <p className="form-field__error" id={errorId}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

FormField.propTypes = {
  id: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  error: PropTypes.string,
};
