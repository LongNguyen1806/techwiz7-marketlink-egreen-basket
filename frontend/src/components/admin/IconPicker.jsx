import { useState } from 'react';
import { ImagePlus } from 'lucide-react';

import { CategoryIcon } from '../common/badges/CategoryIcon';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '../ui/DropdownMenu';
import { CATEGORY_ICON_NAMES, categoryIconLabel } from '../../utils/categoryIcon';
import '../../styles/admin/IconPicker.css';

export function freeIcons(taken = {}, keep = '') {
  return CATEGORY_ICON_NAMES.filter((name) => name === keep || !taken[name]);
}

export function IconPicker({ value, onChange, taken = {} }) {
  const [open, setOpen] = useState(false);
  const available = freeIcons(taken, value);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="icon-picker__trigger"
          aria-label={value ? `Icon: ${categoryIconLabel(value)}. Change icon` : 'Choose an icon'}
          title={value ? categoryIconLabel(value) : 'Choose an icon'}
        >
          {value ? (
            <CategoryIcon icon={value} className="icon-picker__icon" />
          ) : (
            <ImagePlus className="icon-picker__icon" aria-hidden="true" />
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="icon-picker__menu">
        <DropdownMenuLabel className="icon-picker__menu-label">
          Free icons ({available.length})
        </DropdownMenuLabel>
        {available.length === 0 ? (
          <p className="icon-picker__empty">
            Every icon is in use. Delete a category to free one up.
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
                  onClick={() => {
                    onChange(name);
                    setOpen(false);
                  }}
                >
                  <CategoryIcon icon={name} className="icon-picker__icon" />
                </button>
              );
            })}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
