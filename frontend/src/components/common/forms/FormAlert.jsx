import PropTypes from 'prop-types';
import { AlertCircle } from 'lucide-react';
import './FormAlert.css';


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
