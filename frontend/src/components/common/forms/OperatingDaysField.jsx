import PropTypes from 'prop-types';
import './OperatingDaysField.css';

/** ISO weekdays, the same numbering `normalize_operating_days` expects: Monday = 1 … Sunday = 7. */
const WEEKDAYS = [
  { value: 1, name: 'Monday', short: 'Mon' },
  { value: 2, name: 'Tuesday', short: 'Tue' },
  { value: 3, name: 'Wednesday', short: 'Wed' },
  { value: 4, name: 'Thursday', short: 'Thu' },
  { value: 5, name: 'Friday', short: 'Fri' },
  { value: 6, name: 'Saturday', short: 'Sat' },
  { value: 7, name: 'Sunday', short: 'Sun' },
];

/**
 * The days a stall is open (D-031). A pickup slot can only fall on a day that is both a market day
 * and one of these, so the stall has to pick at least one — the serializer refuses an empty list.
 * Sorted on the way out, matching what the backend stores.
 */
export function OperatingDaysField({ id = 'operating-days', value = [], onChange, error, hint }) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  function toggle(day, checked) {
    const next = checked ? [...value, day] : value.filter((current) => current !== day);
    onChange(next.sort((a, b) => a - b));
  }

  return (
    <fieldset className="operating-days" aria-describedby={error ? errorId : hint ? hintId : undefined}>
      <legend className="operating-days__legend">Operating days</legend>

      {hint ? (
        <p className="operating-days__hint" id={hintId}>
          {hint}
        </p>
      ) : null}

      <div className="operating-days__list">
        {WEEKDAYS.map((day) => (
          <label key={day.value} className="operating-days__option">
            <input
              type="checkbox"
              className="operating-days__input"
              aria-label={day.name}
              checked={value.includes(day.value)}
              onChange={(event) => toggle(day.value, event.target.checked)}
            />
            <span className="operating-days__day" aria-hidden>
              {day.short}
            </span>
          </label>
        ))}
      </div>

      {error ? (
        <p className="operating-days__error" id={errorId}>
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}

OperatingDaysField.propTypes = {
  id: PropTypes.string,
  value: PropTypes.arrayOf(PropTypes.number),
  onChange: PropTypes.func.isRequired,
  error: PropTypes.string,
  hint: PropTypes.string,
};
