import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useAdminCustomer, useUpdateCustomer } from "../../hooks/queries/admin/useAdminCustomers";
import { ProfileEditDialog, VN_PHONE } from "../../components/admin/ProfileEditDialog";
import { ChangeLogPanel } from "../../components/admin/ChangeLogPanel";
import { EmptyState } from "../../components/feedback/EmptyState";
import { PageHeader } from "../../components/common/PageHeader";
import { PageSkeleton } from "../../components/feedback/PageSkeleton";
import { StatusBadge } from "../../components/common/StatusBadge";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/Card";
import { formatDate, formatDateTime, formatMoney } from "../../utils/formatters";

import "../../styles/admin/AdminCustomerDetailPage.css";

export default function AdminCustomerDetailPage() {
  const { id = "" } = useParams();
  const customerId = Number(id);
  const query = useAdminCustomer(customerId);
  const update = useUpdateCustomer(customerId);
  const [editing, setEditing] = useState(false);

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError || !query.data) {
    return <EmptyState title='Customer not found' actionLabel='Try again' onAction={() => query.refetch()} />;
  }

  const c = query.data;

  return (
    <div className='admin-customer-detail-page'>
      <PageHeader
        title={c.full_name}
        description={c.email}
        actions={
          <>
            <Button variant='outline' onClick={() => setEditing(true)}>
              Edit details
            </Button>
            <Button asChild variant='outline'>
              <Link to='/admin/customers'>← Back to list</Link>
            </Button>
          </>
        }
      />

      <ProfileEditDialog
        open={editing}
        onOpenChange={setEditing}
        title='Edit customer details'
        note='Locking an account is a separate action, from the customer list.'
        signInEmail={c.email}
        pending={update.isPending}
        onSave={(values) => update.mutateAsync(values)}
        fields={[
          { required: true, name: "full_name", label: "Full name", value: c.full_name, minLength: 2, maxLength: 100 },
          { required: true, name: "phone", label: "Phone", value: c.phone ?? "", type: "tel", pattern: VN_PHONE, patternMessage: "Enter a Vietnamese mobile number, e.g. 0912345678." },
          { required: true, name: "address", label: "Address", value: c.address ?? "", minLength: 5, maxLength: 255 },
        ]}
      />

      <div className='page-primitive__actions-row'>
        <Badge variant={c.is_active ? "success" : "danger"}>{c.is_active ? "Active" : "Locked"}</Badge>
        {c.at_risk ? <Badge variant='warning'>At risk</Badge> : null}
        {c.deactivation_reason ? <span className='page-primitive__danger-sm'>{c.deactivation_reason}</span> : null}
      </div>

      <div className='page-primitive__stat-grid-3'>
        <Card>
          <CardHeader className='page-primitive__card-header-tight'>
            <CardTitle className='page-primitive__card-title-muted'>Total orders</CardTitle>
          </CardHeader>
          <CardContent className='page-primitive__stat-value'>{c.total_orders}</CardContent>
        </Card>
        <Card>
          <CardHeader className='page-primitive__card-header-tight'>
            <CardTitle className='page-primitive__card-title-muted'>Open orders</CardTitle>
          </CardHeader>
          <CardContent className='page-primitive__stat-value'>{c.open_orders}</CardContent>
        </Card>
        <Card>
          <CardHeader className='page-primitive__card-header-tight'>
            <CardTitle className='page-primitive__card-title-muted'>No-shows</CardTitle>
          </CardHeader>
          <CardContent className='page-primitive__stat-value'>{c.no_show_count}</CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent className='admin-customer-detail-page__profile'>
          <p>Phone: {c.phone || "—"}</p>
          <p>Address: {c.address || "—"}</p>
          <p>Joined: {formatDateTime(c.date_joined)}</p>
        </CardContent>
      </Card>

      {c.auto_lock ? (
        <Card className='admin-customer-detail-page__auto-lock'>
          <CardHeader>
            <CardTitle>Locked automatically</CardTitle>
          </CardHeader>
          <CardContent>
            <p className='page-primitive__muted-sm'>
              The system locked this account on {formatDateTime(c.auto_lock.locked_at)} after these
              pickups were missed. Unlocking starts the count again from zero.
            </p>
            <ul className='admin-customer-detail-page__orders'>
              {c.auto_lock.orders.map((order) => (
                <li key={order.id} className='admin-customer-detail-page__order'>
                  <Link to={`/admin/orders?q=${order.id}`}>#{order.id}</Link>
                  <span>{order.stall_name}</span>
                  <span>{order.market_name}</span>
                  <span>{formatDate(order.pickup_date)}</span>
                  <span>{formatMoney(order.total_amount)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <ChangeLogPanel model="customer_profile" id={customerId} />

      <Card>
        <CardHeader>
          <CardTitle>Recent orders</CardTitle>
        </CardHeader>
        <CardContent>
          {c.recent_orders?.length === 0 ? (
            <p className='page-primitive__muted-sm'>No orders yet.</p>
          ) : (
            <ul className='admin-customer-detail-page__orders'>
              {c.recent_orders?.map((order) => (
                <li key={order.id} className='admin-customer-detail-page__order'>
                  <span>#{order.id}</span>
                  <StatusBadge status={order.status} />
                  <span>{formatDate(order.pickup_date)}</span>
                  <span>{formatMoney(order.total_amount)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
