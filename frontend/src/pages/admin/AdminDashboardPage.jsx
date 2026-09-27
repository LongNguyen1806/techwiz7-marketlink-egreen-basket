import { Link } from 'react-router-dom';
import {
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';

import {
  useAdminDashboard,
  useDashboardApproveFarmer,
  useDashboardRejectFarmer,
} from '../../hooks/queries/admin/useAdminDashboard';
import { EmptyState } from '@/components/common/feedback/EmptyState';
import { PageHeader } from '@/components/common/layout/PageHeader';
import { PageSkeleton } from '@/components/common/feedback/PageSkeleton';
import { Button } from '@/components/common/forms/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/cards/Card';
import { orderStatusLabel } from '@/utils/labels';

import './AdminDashboardPage.css';

// Counts an admin can act on today, each linking to the screen that acts on it. Separate
// from the totals below, which describe the platform rather than ask for anything.
const ATTENTION = [
  {
    key: 'stalls_awaiting_approval',
    label: 'Stalls awaiting approval',
    to: '/admin/farmers?status=PENDING',
  },
  { key: 'flags_open', label: 'In the follow-up queue', to: '/admin/queue' },
  { key: 'customers_at_risk', label: 'Shoppers at risk', to: '/admin/customers' },
  { key: 'hidden_products', label: 'Products hidden', to: '/admin/moderation' },
  { key: 'markets_closed', label: 'Markets closed', to: '/admin/markets' },
];

const PIE_COLORS = ['#15803d', '#ca8a04', '#2563eb', '#dc2626', '#64748b', '#7c3aed'];

export default function AdminDashboardPage() {
  const query = useAdminDashboard();
  const approve = useDashboardApproveFarmer();
  const reject = useDashboardRejectFarmer();

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError || !query.data) {
    return (
      <EmptyState
        title="Overview couldn't be loaded"
        actionLabel="Try again"
        onAction={() => query.refetch()}
      />
    );
  }

  const data = query.data;
  const cards = [
    { label: 'Stalls', value: data.totals.farmers },
    { label: 'Awaiting approval', value: data.totals.farmers_pending },
    { label: 'Shoppers', value: data.totals.customers },
    { label: 'Active markets', value: data.totals.markets_active },
    // The chart below covers 30 days, so this total says out loud that it does not.
    { label: 'Orders all time', value: data.totals.orders },
  ];

  // Spelt out here so the legend, the slice labels and the tooltip all read the same.
  const ordersByStatus = data.orders_by_status.map((row) => ({
    ...row,
    name: orderStatusLabel(row.status),
  }));

  return (
    <div className="admin-dashboard-page">
      <PageHeader
        title="Platform overview"
        description="Monitor stalls, markets, orders, and content that needs attention."
      />

      {data.needs_attention ? (
        <section className="admin-dashboard-page__attention">
          <h2 className="admin-dashboard-page__attention-title">Waiting for you</h2>
          <div className="admin-dashboard-page__attention-grid">
            {ATTENTION.map((item) => {
              const count = data.needs_attention[item.key] ?? 0;
              return (
                <Link
                  key={item.key}
                  to={item.to}
                  className={`admin-dashboard-page__task${count ? ' admin-dashboard-page__task--live' : ''}`}
                >
                  <b>{count}</b>
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </div>
        </section>
      ) : null}

      <div className="page-primitive__stat-grid-5">
        {cards.map((item) => (
          <Card key={item.label}>
            <CardHeader className="page-primitive__card-header-tight">
              <CardTitle className="page-primitive__card-title-muted">
                {item.label}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="page-primitive__stat-value">{item.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="page-primitive__charts-row">
        <Card>
          <CardHeader>
            <CardTitle>Orders · last 30 days</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__chart-h">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.orders_by_day}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#15803d" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Orders by status</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__chart-h">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={ordersByStatus}
                  dataKey="count"
                  nameKey="name"
                  outerRadius={80}
                  label
                >
                  {ordersByStatus.map((entry, index) => (
                    <Cell
                      key={entry.status}
                      fill={PIE_COLORS[index % PIE_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="page-primitive__card-header-row">
          <CardTitle>Stalls awaiting approval</CardTitle>
          <Button asChild size="sm" variant="outline">
            <Link to="/admin/farmers?status=PENDING">View all</Link>
          </Button>
        </CardHeader>
        <CardContent className="admin-dashboard-page__pending-list">
          {data.pending_farmers.length === 0 ? (
            <p className="page-primitive__muted-sm">No pending profiles.</p>
          ) : (
            data.pending_farmers.map((f) => (
              <div key={f.id} className="page-primitive__row-card">
                <div>
                  <Link to={`/admin/farmers/${f.id}`} className="page-primitive__link">
                    {f.stall_name}
                  </Link>
                  <p className="page-primitive__muted-sm">{f.email}</p>
                </div>
                <div className="page-primitive__actions-row">
                  <Button
                    size="sm"
                    loading={approve.isPending}
                    onClick={() => approve.mutate(f.id)}
                  >
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    loading={reject.isPending}
                    onClick={() => reject.mutate(f.id)}
                  >
                    Reject
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
