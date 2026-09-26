import PropTypes from 'prop-types';
import { Button } from '../ui/Button';
import { DAYS_OF_WEEK } from '../../utils/labels';

/** Toggle buttons for ISO weekdays (Mon = 1 ... Sun = 7). `value` stays sorted. */
export function OperatingDaysPicker({ value, onChange, onBlur, disabled = false }) {
  const toggle = (day) => {
    const next = value.includes(day) ? value.filter((d) => d !== day) : [...value, day];
    onChange(next.sort((a, b) => a - b));
  };

  return (
    <div className="page-primitive__actions-row" role="group" aria-label="Operating days">
      {DAYS_OF_WEEK.map((day) => {
        const selected = value.includes(day.value);
        return (
          <Button
            key={day.value}
            type="button"
            size="sm"
            variant={selected ? 'default' : 'outline'}
            aria-pressed={selected}
            aria-label={day.long}
            disabled={disabled}
            onClick={() => toggle(day.value)}
            onBlur={onBlur}
          >
            {day.short}
          </Button>
        );
      })}
    </div>
  );
}

OperatingDaysPicker.propTypes = {
  value: PropTypes.arrayOf(PropTypes.number).isRequired,
  onChange: PropTypes.func.isRequired,
  onBlur: PropTypes.func,
  disabled: PropTypes.bool,
};
