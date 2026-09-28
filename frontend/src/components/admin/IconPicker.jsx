import { CategoryIcon } from '../common/badges/CategoryIcon';
import { CATEGORY_ICON_NAMES, categoryIconLabel } from '../../utils/categoryIcon';
import '../../styles/admin/IconPicker.css';
export function IconPicker({ value, onChange, taken = {} }) {
  const available = CATEGORY_ICON_NAMES.filter((name) => name === value || !taken[name]);

  return (
    <div className="icon-picker">
      <p className="page-primitive__label-xs">Icon</p>
      {available.length === 0 ? (
        <p className="page-primitive__muted-xs">
          Every icon is in use. Free one up by deleting a category, or ask a developer to add
          more.
        </p>
      ) : (
        <div className="icon-picker__grid" role="radiogroup" aria-label="Category icon">
          {available.map((name) => {
            const selected = name === value;
            return (
              <button
                key={name}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={categoryIconLabel(name)}
                title={categoryIconLabel(name)}
                className={`icon-picker__option${selected ? ' icon-picker__option--on' : ''}`}
                onClick={() => onChange(name)}
              >
                <CategoryIcon icon={name} className="icon-picker__icon" />
              </button>
            );
          })}
        </div>
      )}
      <p className="page-primitive__muted-xs">
        Each category wears its own icon, so only the free ones are listed.
      </p>
    </div>
  );
}
