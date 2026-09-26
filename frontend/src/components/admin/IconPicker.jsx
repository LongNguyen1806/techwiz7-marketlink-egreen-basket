import { CategoryIcon } from '../common/badges/CategoryIcon';
import { CATEGORY_ICON_NAMES } from '../../utils/categoryIcon';
import '../../styles/admin/IconPicker.css';


export function IconPicker({ value, onChange }) {
  return (
    <div className="icon-picker">
      <p className="page-primitive__label-xs">Icon</p>
      <div className="icon-picker__grid" role="radiogroup" aria-label="Category icon">
        {CATEGORY_ICON_NAMES.map((name) => {
          const selected = name === value;
          return (
            <button
              key={name}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={name}
              title={name}
              className={`icon-picker__option${selected ? ' icon-picker__option--on' : ''}`}
              onClick={() => onChange(name)}
            >
              <CategoryIcon icon={name} className="icon-picker__icon" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
