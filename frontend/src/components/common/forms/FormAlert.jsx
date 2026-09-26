import PropTypes from 'prop-types';
import { AlertCircle } from 'lucide-react';
import './FormAlert.css';

/**
 * Whatever the server rejected that belongs to no single box: a wrong password, a locked account
 * (D-024). It is a live region, so submitting and failing announces itself without moving focus.
 */
export function FormAlert({ message }) {
  if (!message) return null;

  return (
    <p className="form-alert" role="alert">
      <AlertCircle className="form-alert__icon" strokeWidth={1.75} aria-hidden />
      {message}
    </p>
  );
}

FormAlert.propTypes = {
  message: PropTypes.string,
};
