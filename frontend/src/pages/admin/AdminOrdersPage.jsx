import { useState } from 'react';

import { useAdminOrders } from '../../hooks/queries/admin/useAdminOrders';
import { useDebouncedValue } from '@/hooks/common/useDebouncedValue';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { SortableTh } from '@/components/common/SortableTh';
import { formatDate, formatDateTime, formatMoney } from '@/utils/formatters';
import { orderStatusLabel } from '@/utils/labels';

import '@/components/common/table/FilterBar.css';
import './AdminOrdersPage.css';

const STATUSES = [
  'PLACED',
  'ACCEPTED',
  'READY_FOR_PICKUP',
  'COMPLETED',
  'DECLINED',
  'CANCELLED',
  'EXPIRED',
  'NO_SHOW',
];

export default function AdminOrdersPage() {
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [ordering, setOrdering] = useState(undefined);
  const [page, setPage] = useState(1);

  const searchTerm = useDebouncedValue(q);

  const query = useAdminOrders({
    q: searchTerm || undefined,
    status: status || undefined,
    from: from || undefined,
    to: to || undefined,
    ordering,
    page,
    page_size: 20,
  });

  return (
    <div className="admin-orders-page">
      <PageHeader
        title="Orders"
        description="Look up an order to answer a question about it. This screen never changes one."
      />

      <div className="page-primitive__actions-row">
        <Input
          label="Order number, name, phone or stall"
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(1);
          }}
          className="page-primitive__input-narrow"
        />
        <div className="admin-orders-page__field">
          <Label className="page-primitive__label-xs" htmlFor="order-status">
            Status
          </Label>
          <select
            id="order-status"
            className="page-primitive__select"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {orderStatusLabel(value)}
              </option>
            ))}
          </select>
        </div>
        <Input
          type="date"
          label="Pickup from"
          value={from}
          onChange={(event) => setFrom(event.target.value)}
          className="page-primitive__input-auto"
        />
        <Input
          type="date"
          label="Pickup to"
          value={to}
          onChange={(event) => setTo(event.target.value)}
          className="page-primitive__input-auto"
        />
        <Button
          size="sm"
          variant="ghost"
          className="filter-bar__clear"
          disabled={!q && !status && !from && !to}
          onClick={() => {
            setQ('');
            setStatus('');
            setFrom('');
            setTo('');
            setPage(1);
          }}
        >
          Clear
        </Button>
      </div>

      {query.isLoading ? (
        <PageSkeleton />
      ) : !query.data?.results.length ? (
        <EmptyState title="No orders match this search" />
      ) : (
        <>
          <div className="page-primitive__table-wrap">
            <table className="page-primitive__table page-primitive__table-min-800">
              <thead className="page-primitive__table-head">
                <tr>
                  <th className="page-primitive__table-th">Order</th>
                  <th className="page-primitive__table-th">Shopper</th>
                  <th className="page-primitive__table-th">Stall</th>
                  <SortableTh column="status" current={ordering} onSort={setOrdering}>
                    Status
                  </SortableTh>
                  <SortableTh
                    column="pickup_date"
                    current={ordering}
                    onSort={setOrdering}
                  >
                    Pickup
                  </SortableTh>
                  <SortableTh
                    column="total_amount"
                    current={ordering}
                    onSort={setOrdering}
                  >
                    Total
                  </SortableTh>
                  <SortableTh column="created_at" current={ordering} onSort={setOrdering}>
                    Placed
                  </SortableTh>
                </tr>
              </thead>
              <tbody>
                {query.data.results.map((order) => (
                  <tr key={order.id} className="page-primitive__table-row">
                    <td className="page-primitive__table-td page-primitive__font-medium">
                      #{order.id}
                    </td>
                    <td className="page-primitive__table-td">
                      <p>{order.customer?.full_name ?? '—'}</p>
                      <p className="page-primitive__muted-xs">{order.customer?.phone}</p>
                    </td>
                    <td className="page-primitive__table-td">
                      {order.farmer?.stall_name ?? '—'}
                    </td>
                    <td className="page-primitive__table-td">
                      <StatusBadge status={order.status} />
                    </td>
                    <td className="page-primitive__table-td">
                      {formatDate(order.pickup_date)}
                    </td>
                    <td className="page-primitive__table-td">
                      {formatMoney(order.total_amount)}
                    </td>
                    <td className="page-primitive__table-td page-primitive__muted-xs">
                      {formatDateTime(order.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="admin-orders-page__pagination">
            <span>
              Page {query.data.page}/{query.data.total_pages} · {query.data.count} orders
            </span>
            <div className="page-primitive__actions-row">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= query.data.total_pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
