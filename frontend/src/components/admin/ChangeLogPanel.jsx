import { useAdminChangeLog } from '@/hooks/queries/admin/useAdminChangeLog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { formatDateTime } from '@/utils/formatters';
import '@/styles/admin/ChangeLogPanel.css';

const TYPE_LABEL = {
  CREATED: 'Created',
  UPDATED: 'Edited',
  DELETED: 'Deleted',
};

function fieldName(field) {
  const words = (field || '').replaceAll('_', ' ').toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function shown(value) {
  if (value === null || value === undefined || value === '') return 'empty';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (Array.isArray(value)) return value.join(', ') || 'empty';
  return String(value);
}

/** The audit trail: how this one record changed over time. */
export function ChangeLogPanel({ model, id }) {
  const query = useAdminChangeLog(model, id);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change history</CardTitle>
      </CardHeader>
      <CardContent className="change-log__body">
        {query.isLoading ? (
          <p className="page-primitive__muted-sm">Loading…</p>
        ) : !query.data?.length ? (
          <p className="page-primitive__muted-sm">No changes recorded yet.</p>
        ) : (
          query.data.map((entry) => (
            <div key={entry.history_id} className="change-log__entry">
              <p className="change-log__head">
                <span className="page-primitive__font-medium">
                  {TYPE_LABEL[entry.change_type] || entry.change_type}
                </span>
                <span className="page-primitive__muted-sm">
                  {formatDateTime(entry.date)} · {entry.user?.email ?? 'System'}
                </span>
              </p>
              {entry.reason ? (
                <p className="page-primitive__muted-sm">{entry.reason}</p>
              ) : null}
              {entry.changes?.length ? (
                <ul className="change-log__changes">
                  {entry.changes.map((change) => (
                    <li key={change.field} className="change-log__change">
                      <span className="change-log__field">{fieldName(change.field)}</span>
                      <span className="change-log__old">{shown(change.old)}</span>
                      <span aria-hidden>→</span>
                      <span className="change-log__new">{shown(change.new)}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
