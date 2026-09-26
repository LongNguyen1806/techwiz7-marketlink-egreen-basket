import { Label } from '@/components/ui/Label';
import '@/styles/common/SortSelect.css';

/** Sorting for the lists drawn as cards rather than tables. */
export function SortSelect({ id, options, value, onChange }) {
  return (
    <div className="sort-select">
      <Label className="page-primitive__label-xs" htmlFor={id}>
        Sort by
      </Label>
      <select
        id={id}
        className="page-primitive__select"
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value || undefined)}
      >
        <option value="">Default</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
