import { useState } from 'react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../ui/Dialog';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Textarea } from '../ui/Textarea';
import { ApiError } from '../../lib/ApiError';
import '../../styles/admin/ProfileEditDialog.css';

export function ProfileEditDialog({
  open,
  onOpenChange,
  title,
  note,
  fields = [],
  pending = false,
  onSave,
}) {
  const [values, setValues] = useState({});
  const [errors, setErrors] = useState({});

  const [seededFor, setSeededFor] = useState(null);
  if (open !== seededFor) {
    setSeededFor(open);
    if (open) {
      setValues(Object.fromEntries(fields.map((field) => [field.name, field.value])));
      setErrors({});
    }
  }

  const submit = async (event) => {
    event.preventDefault();
    setErrors({});
    const changed = Object.fromEntries(
      fields
        .filter((field) => values[field.name] !== field.value)
        .map((field) => [field.name, values[field.name]]),
    );
    if (Object.keys(changed).length === 0) {
      onOpenChange(false);
      return;
    }
    try {
      await onSave(changed);
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = ApiError.fromUnknown(error).fieldErrors || {};
      setErrors(
        Object.fromEntries(
          Object.entries(fieldErrors).map(([key, messages]) => [key, String(messages[0] ?? '')]),
        ),
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{note}</DialogDescription>
        </DialogHeader>
        <form className="profile-edit-dialog__form" onSubmit={submit}>
          {fields.map((field) => (
            <div key={field.name} className="profile-edit-dialog__field">
              {field.multiline ? (
                <Textarea
                  id={`edit-${field.name}`}
                  placeholder={field.label}
                  value={values[field.name] ?? ''}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.value }))
                  }
                />
              ) : (
                <Input
                  id={`edit-${field.name}`}
                  type={field.type ?? 'text'}
                  label={field.label}
                  requiredMark={field.required}
                  value={values[field.name] ?? ''}
                  onChange={(event) =>
                    setValues((current) => ({ ...current, [field.name]: event.target.value }))
                  }
                />
              )}
              {errors[field.name] ? (
                <p className="page-primitive__error">{errors[field.name]}</p>
              ) : null}
            </div>
          ))}
          <div className="profile-edit-dialog__actions">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={pending}>
              Save changes
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
