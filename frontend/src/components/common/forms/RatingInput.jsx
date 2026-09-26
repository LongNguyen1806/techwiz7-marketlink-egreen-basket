import PropTypes from 'prop-types';
import { Star } from 'lucide-react';
import { cn } from '../../../lib/cn';
import './RatingInput.css';

const SCORES = [1, 2, 3, 4, 5];


export function RatingInput({ name, value, onChange, disabled = false }) {
  return (
    <fieldset className="rating-input" disabled={disabled}>
      <legend className="rating-input__legend">Rating</legend>
      {SCORES.map((score) => (
        <label className="rating-input__option" key={score}>
          <input
            type="radio"
            className="rating-input__radio"
            name={name}
            value={score}
            aria-label={`${score} star${score > 1 ? 's' : ''}`}
            checked={value === score}
            disabled={disabled}
            onChange={() => onChange(score)}
          />
          <Star
            className={cn('rating-input__star', value !== null && score <= value && 'is-filled')}
            aria-hidden
          />
        </label>
      ))}
    </fieldset>
  );
}

RatingInput.propTypes = {
  name: PropTypes.string.isRequired,
  value: PropTypes.number,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};
