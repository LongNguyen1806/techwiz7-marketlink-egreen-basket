import { CategoryIcon } from '@/components/common/badges/CategoryIcon';
import { CATEGORY_ICON_NAMES, categoryIconLabel } from '@/utils/categoryIcon';

import './IconPicker.css';

/**
 * A category stores its icon by name, and that name has to be one of a known set and one no
 * other category already wears.
 *
 * Typing it from memory was guesswork, so the admin picks from the set the app can draw, and
 * only from what is still free. An icon another category wears is not shown at all: every
 * square in this grid is one that can actually be chosen, so there is nothing to explain and
 * nothing to click that would come back refused.
 *
 * `taken` maps an icon name to the category using it. The value currently selected always
 * stays, or editing a category would hide the very icon it already has.
 */
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
