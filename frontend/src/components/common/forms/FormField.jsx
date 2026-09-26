import PropTypes from 'prop-types';
import { Input } from '../../ui/Input';
import './FormField.css';


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
