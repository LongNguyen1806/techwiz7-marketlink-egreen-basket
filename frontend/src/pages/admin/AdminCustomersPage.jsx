import { useState } from 'react';
import { AccountsTabs } from '../../components/admin/AccountsTabs';

import { useCsvDownload } from '@/hooks/useCsvDownload';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import { cn } from '@/lib/cn';
import {
  fetchCustomerImpact,
  useActivateCustomer,
  useAdminCustomers,
  useDeactivateCustomer,
} from '../../hooks/queries/admin/useAdminCustomers';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { FilterBar } from '@/components/common/table/FilterBar';
import { SortableTh } from '@/components/common/SortableTh';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';

import './AdminCustomersPage.css';

const REASON_MIN_LENGTH = 5;

const CUSTOMER_FILTERS = [
  { name: 'q', label: 'Search name, email or phone', type: 'search' },
  {
    name: 'is_active',
    label: 'Account',
    type: 'select',
    allLabel: 'Active and locked',
    options: [
      { value: 'true', label: 'Active' },
      { value: 'false', label: 'Locked' },
    ],
  },
  {
    name: 'at_risk',
    label: 'Risk',
    type: 'select',
    allLabel: 'Everyone',
    options: [{ value: 'true', label: 'At risk only' }],
  },
];

export default function AdminCustomersPage() {
  const csv = useCsvDownload('customers');
  const [deactivateId, setDeactivateId] = useState(null);
  const [reason, setReason] = useState('');
  const [impactText, setImpactText] = useState('');

  const [ordering, setOrdering] = useState(undefined);
  const [filters, setFilters] = useState({});

  const query = useAdminCustomers({ ...filters, ordering });
  const deactivate = useDeactivateCustomer();
  const activate = useActivateCustomer();

  const openDeactivate = async (id) => {
    try {
      const impact = await fetchCustomerImpact(id);
      setImpactText(
        `${impact.open_orders.total} open orders will be cancelled. Stock of the ${impact.open_orders.ACCEPTED + impact.open_orders.READY_FOR_PICKUP} accepted orders goes back to ${impact.affected_farmers} farmers.`,
      );
      setDeactivateId(id);
      setReason('');
    } catch (e) {
      toast.error(ApiError.fromUnknown(e).friendlyMessage);
    }
  };

  return (
    <div className="admin-customers-page">
      <PageHeader
        title="Accounts"
        actions={
          <Button
            size="sm"
            variant="outline"
            loading={csv.pending}
            onClick={() => csv.download({ ...filters, ordering })}
          >
            Export CSV
          </Button>
        }
        description="Lock or unlock accounts and monitor no-show history."
      />
      <AccountsTabs />
      <FilterBar
        fields={CUSTOMER_FILTERS}
        value={filters}
        onChange={setFilters}
        onReset={() => setFilters({})}
      />

      {query.isLoading ? (
        <PageSkeleton />
      ) : !query.data?.results.length ? (
        <EmptyState title="No customers to show" />
      ) : (
        <div className="page-primitive__table-wrap">
          <table className="page-primitive__table page-primitive__table-min-720">
            <thead className="page-primitive__table-head">
              <tr>
                <SortableTh column="full_name" current={ordering} onSort={setOrdering}>
                  Customer
                </SortableTh>
                <SortableTh column="total_orders" current={ordering} onSort={setOrdering}>
                  Orders
                </SortableTh>
                <SortableTh
                  column="no_show_count"
                  current={ordering}
                  onSort={setOrdering}
                >
                  No-show
                </SortableTh>
                <SortableTh column="is_active" current={ordering} onSort={setOrdering}>
                  Status
                </SortableTh>
                <th className="page-primitive__table-th">Lock reason</th>
                <th className="page-primitive__table-th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {query.data.results.map((c) => (
                <tr key={c.id} className="page-primitive__table-row">
                  <td className="page-primitive__table-td">
                    <Link
                      to={`/admin/customers/${c.id}`}
                      className="page-primitive__link"
                    >
                      {c.full_name}
                    </Link>
                    <p className="page-primitive__muted-xs">{c.email}</p>
                  </td>
                  <td className="page-primitive__table-td">{c.total_orders}</td>
                  <td className="page-primitive__table-td">
                    <span
                      className={cn(
                        c.no_show_count >= 3 && 'page-primitive__no-show-warn',
                      )}
                    >
                      {c.no_show_count}
                    </span>
                  </td>
                  <td className="page-primitive__table-td">
                    <Badge variant={c.is_active ? 'success' : 'danger'}>
                      {c.is_active ? 'Active' : 'Locked'}
                    </Badge>
                    {c.at_risk ? (
                      <Badge variant="warning" className="admin-customers-page__risk">
                        At risk
                      </Badge>
                    ) : null}
                  </td>
                  <td className="page-primitive__table-td page-primitive__muted-xs">
                    {c.deactivation_reason ?? '—'}
                  </td>
                  <td className="page-primitive__table-td">
                    {c.is_active ? (
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => openDeactivate(c.id)}
                      >
                        Lock
                      </Button>
                    ) : (
                      <Button size="sm" onClick={() => activate.mutate(c.id)}>
                        Unlock
                      </Button>
                    )}
                    <Button asChild size="sm" variant="outline">
                      <Link to={`/admin/customers/${c.id}`}>Details</Link>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(deactivateId)}
        onOpenChange={(open) => {
          if (!open) setDeactivateId(null);
        }}
        title="Lock this customer"
        description={impactText}
        destructive
        loading={deactivate.isPending}
        onConfirm={() => {
          if (!deactivateId || reason.trim().length < REASON_MIN_LENGTH) {
            toast.error(`Lock reason must be at least ${REASON_MIN_LENGTH} characters`);
            return;
          }
          deactivate.mutate(
            { id: deactivateId, reason },
            {
              onSuccess: () => setDeactivateId(null),
            },
          );
        }}
      >
        <Textarea
          className="admin-customers-page__dialog-field"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Lock reason…"
        />
      </ConfirmDialog>
    </div>
  );
}
