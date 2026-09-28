import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { useDebouncedValue } from '@/hooks/common/useDebouncedValue';

import './FilterBar.css';

export function FilterBar({ fields, value, onChange, onReset }) {
  const [text, setText] = useState(value.q ?? '');
  const debounced = useDebouncedValue(text);

  useEffect(() => {
    if ((value.q ?? '') === debounced) return;
    onChange({ ...value, q: debounced || undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const set = (name, next) => onChange({ ...value, [name]: next || undefined });
  const isDirty = Object.entries(value).some(([, v]) => v !== undefined && v !== '');

  return (
    <div className="filter-bar">
      {fields.map((field) => {
        if (field.type === 'search') {
          return (
            <Input
              key={field.name}
              label={field.label}
              value={text}
              onChange={(event) => setText(event.target.value)}
              className="filter-bar__search"
            />
          );
        }
        if (field.type === 'date') {
          return (
            <Input
              key={field.name}
              type="date"
              label={field.label}
              value={value[field.name] ?? ''}
              onChange={(event) => set(field.name, event.target.value)}
              className="filter-bar__date"
            />
          );
        }
        return (
          <div key={field.name} className="filter-bar__field">
            <Label className="page-primitive__label-xs" htmlFor={`filter-${field.name}`}>
              {field.label}
            </Label>
            <select
              id={`filter-${field.name}`}
              className="page-primitive__select"
              value={value[field.name] ?? ''}
              onChange={(event) => set(field.name, event.target.value)}
            >
              <option value="">{field.allLabel ?? 'All'}</option>
              {field.options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        );
      })}

      <Button
        size="sm"
        variant="ghost"
        className="filter-bar__clear"
        disabled={!isDirty}
        onClick={() => {
          setText('');
          onReset();
        }}
      >
        Clear
      </Button>
    </div>
  );
}
