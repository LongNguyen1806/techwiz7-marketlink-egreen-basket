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

// The rules registration uses, checked before the save so the admin sees them at once.
// The server checks the same rules again; this only saves a round trip.
export const VN_PHONE = /^(0|\+84)(3|5|7|8|9)\d{8}$/;

function problemWith(field, raw) {
  const value = (raw ?? '').trim();
  if (field.required && !value) return `${field.label} is required.`;
  if (!value) return null;
  if (field.minLength && value.length < field.minLength) {
    return `${field.label} must be at least ${field.minLength} characters.`;
  }
  if (field.maxLength && value.length > field.maxLength) {
    return `${field.label} must be at most ${field.maxLength} characters.`;
  }
  if (field.pattern && !field.pattern.test(value.replace(/[\s.-]/g, ''))) {
    return field.patternMessage ?? `${field.label} is not valid.`;
  }
  return null;
}

export function ProfileEditDialog({
  open,
  onOpenChange,
  title,
  note,
  // Shown but never editable: the email is what the account signs in with, and there is no
  // endpoint for changing someone else's.
  signInEmail,
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
    const problems = Object.fromEntries(
      fields
        .map((field) => [field.name, problemWith(field, values[field.name])])
        .filter(([, problem]) => problem),
    );
    if (Object.keys(problems).length > 0) {
      setErrors(problems);
      return;
    }
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
          Object.entries(fieldErrors).map(([key, messages]) => [
            key,
            String(messages[0] ?? ''),
          ]),
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
          {signInEmail ? (
            <div className="profile-edit-dialog__field">
              <Input id="edit-email" label="Email" value={signInEmail} readOnly disabled />
              <p className="page-primitive__muted-xs">
                This is the sign-in address and cannot be changed here.
              </p>
            </div>
          ) : null}
          {fields.map((field) => (
            <div key={field.name} className="profile-edit-dialog__field">
              {field.multiline ? (
                <Textarea
                  id={`edit-${field.name}`}
                  placeholder={field.label}
                  value={values[field.name] ?? ''}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      [field.name]: event.target.value,
                    }))
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
                    setValues((current) => ({
                      ...current,
                      [field.name]: event.target.value,
                    }))
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
