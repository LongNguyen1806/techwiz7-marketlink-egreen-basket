import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';

import { ApiError } from '../../lib/ApiError';
import {
  fetchFarmerImpact,
  useAdminFarmers,
  useApproveFarmer,
  useReinstateFarmer,
  useRejectFarmer,
  useSuspendFarmer,
} from '../../hooks/queries/admin/useAdminFarmers';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Textarea } from '../../components/ui/Textarea';
import { SortableTh } from '../../components/common/SortableTh';
import { farmerStatusLabel, farmerStatusVariant } from '../../utils/labels';

import '../../styles/admin/AdminFarmersPage.css';

const STATUSES = ['PENDING', 'APPROVED', 'REJECTED', 'SUSPENDED'];

function isStatus(v) {
  return v === 'PENDING' || v === 'APPROVED' || v === 'REJECTED' || v === 'SUSPENDED';
}

export default function AdminFarmersPage() {
  const [params, setParams] = useSearchParams();
  const statusParam = params.get('status');
  const status = isStatus(statusParam) ? statusParam : undefined;
  const [q, setQ] = useState(params.get('q') ?? '');
  const [page, setPage] = useState(1);

  const [rejectId, setRejectId] = useState(null);
  const [suspendId, setSuspendId] = useState(null);
  const [reason, setReason] = useState('');
  const [impactText, setImpactText] = useState('');

  const ordering = params.get('ordering') || undefined;
  const sortBy = (next) => {
    const updated = new URLSearchParams(params);
    updated.set('ordering', next);
    setParams(updated);
    setPage(1);
  };

  const query = useAdminFarmers({
    q: params.get('q') || undefined,
    status,
    ordering,
    page,
    page_size: 10,
  });

  const approve = useApproveFarmer();
  const reject = useRejectFarmer();
  const suspend = useSuspendFarmer();
  const reinstate = useReinstateFarmer();

  const openSuspend = async (id) => {
    try {
      const impact = await fetchFarmerImpact(id);
      setImpactText(
        `${impact.open_orders.total} open orders will be declined and ${impact.affected_customers} customers notified. Stock of the ${impact.open_orders.ACCEPTED + impact.open_orders.READY_FOR_PICKUP} accepted orders is returned.`,
      );
      setSuspendId(id);
      setReason('');
    } catch (e) {
      toast.error(ApiError.fromUnknown(e).friendlyMessage);
    }
  };

  return (
    <div className="admin-farmers-page">
      <PageHeader
        title="Farmer stalls"
        description="Approve new growers, suspend accounts, and restore access."
      />

      <form
        className="page-primitive__actions-row"
        onSubmit={(e) => {
          e.preventDefault();
          const next = new URLSearchParams(params);
          if (q) next.set('q', q);
          else next.delete('q');
          setParams(next);
          setPage(1);
        }}
      >
        <Input
          label="Search stall / email"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="page-primitive__input-narrow"
        />
        <select
          className="page-primitive__select"
          value={status ?? ''}
          onChange={(e) => {
            const next = new URLSearchParams(params);
            if (e.target.value) next.set('status', e.target.value);
            else next.delete('status');
            setParams(next);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          {STATUSES.map((value) => (
            <option key={value} value={value}>
              {farmerStatusLabel(value)}
            </option>
          ))}
        </select>
        <Button type="submit" size="sm">
          Filter
        </Button>
      </form>

      {query.isLoading ? (
        <PageSkeleton />
      ) : query.isError ? (
        <EmptyState
          title="Stalls couldn't be loaded"
          actionLabel="Try again"
          onAction={() => query.refetch()}
        />
      ) : !query.data?.results?.length ? (
        <EmptyState title="No farmer stalls yet" />
      ) : (
        <>
          <div className="page-primitive__table-wrap">
            <table className="page-primitive__table page-primitive__table-min-800">
              <thead className="page-primitive__table-head">
                <tr>
                  <SortableTh column="stall_name" current={ordering} onSort={sortBy}>
                    Stall
                  </SortableTh>
                  <SortableTh column="email" current={ordering} onSort={sortBy}>
                    Contact
                  </SortableTh>
                  <SortableTh column="status" current={ordering} onSort={sortBy}>
                    Status
                  </SortableTh>
                  <SortableTh column="open_order_count" current={ordering} onSort={sortBy}>
                    Open orders
                  </SortableTh>
                  <th className="page-primitive__table-th">Actions</th>
                </tr>
              </thead>
              <tbody>
                {query.data.results.map((f) => (
                  <tr key={f.id} className="page-primitive__table-row">
                    <td className="page-primitive__table-td">
                      <Link
                        to={`/admin/farmers/${f.id}`}
                        className="page-primitive__link"
                      >
                        {f.stall_name}
                      </Link>
                      <p className="page-primitive__muted-xs">{f.email}</p>
                    </td>
                    <td className="page-primitive__table-td">
                      <p>{f.email}</p>
                      <p className="page-primitive__muted-xs">{f.phone}</p>
                    </td>
                    <td className="page-primitive__table-td">
                      <Badge variant={farmerStatusVariant(f.status)}>
                        {farmerStatusLabel(f.status)}
                      </Badge>
                    </td>
                    <td className="page-primitive__table-td">{f.open_order_count}</td>
                    <td className="page-primitive__table-td">
                      <div className="page-primitive__actions-row">
                        {f.status === 'PENDING' ? (
                          <>
                            <Button size="sm" onClick={() => approve.mutate(f.id)}>
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setRejectId(f.id);
                                setReason('');
                              }}
                            >
                              Reject
                            </Button>
                          </>
                        ) : null}
                        {f.status === 'APPROVED' ? (
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => openSuspend(f.id)}
                          >
                            Suspend
                          </Button>
                        ) : null}
                        {f.status === 'SUSPENDED' || f.status === 'REJECTED' ? (
                          <Button size="sm" onClick={() => reinstate.mutate(f.id)}>
                            Restore
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="admin-farmers-page__pagination">
            <span>
              Page {query.data.page}/{query.data.total_pages} · {query.data.count} profiles
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

      <ConfirmDialog
        open={Boolean(rejectId)}
        onOpenChange={(open) => {
          if (!open) setRejectId(null);
        }}
        title="Decline stall application"
        description="Share a clear reason (at least 5 characters)."
        destructive
        loading={reject.isPending}
        onConfirm={() => {
          if (!rejectId || reason.trim().length < 5) {
            toast.error('Reason must be at least 5 characters');
            return;
          }
          reject.mutate(
            { id: rejectId, reason },
            {
              onSuccess: () => {
                setRejectId(null);
                setReason('');
              },
            },
          );
        }}
      >
        <Textarea
          className="admin-farmers-page__dialog-field"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </ConfirmDialog>

      <ConfirmDialog
        open={Boolean(suspendId)}
        onOpenChange={(open) => {
          if (!open) setSuspendId(null);
        }}
        title="Suspend this stall"
        description={impactText}
        destructive
        loading={suspend.isPending}
        onConfirm={() => {
          if (!suspendId || reason.trim().length < 5) {
            toast.error('Reason must be at least 5 characters');
            return;
          }
          suspend.mutate(
            { id: suspendId, reason },
            {
              onSuccess: () => {
                setSuspendId(null);
                setReason('');
              },
            },
          );
        }}
      >
        <Textarea
          className="admin-farmers-page__dialog-field"
          placeholder="Suspension reason…"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </ConfirmDialog>
    </div>
  );
}
