import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import {
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import {
  useAdminDashboard,
  useAdminOrdersByMonth,
  useDashboardApproveFarmer,
  useDashboardRejectFarmer,
} from '../../hooks/queries/admin/useAdminDashboard';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { AIReviewSummaryCard } from '@/components/admin/AIReviewSummaryCard';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { orderStatusLabel } from '@/utils/labels';
import { orderStatusColor } from '@/utils/statusColors';

import './AdminDashboardPage.css';

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

function dayOfMonth(value) {
  const [, , day] = String(value).split('-');
  return day ? String(Number(day)) : value;
}

function fullDate(value) {
  const [year, month, day] = String(value).split('-');
  return year && month && day ? `${day}/${month}/${year}` : value;
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function currentMonthKey() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function shiftMonth(key, delta) {
  const [year, month] = key.split('-').map(Number);
  const index = year * 12 + (month - 1) + delta;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, '0')}`;
}

function monthTitle(key) {
  const [year, month] = key.split('-').map(Number);
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

function countLabel({ x, y, value }) {
  if (!value) return null;
  return (
    <text x={x} y={y - 8} textAnchor="middle" fontSize={11} fontWeight={600} fill="#15803d">
      {value}
    </text>
  );
}

export default function AdminDashboardPage() {
  const query = useAdminDashboard();
  const [month, setMonth] = useState(currentMonthKey);
  const monthQuery = useAdminOrdersByMonth(month);
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
    { label: 'Orders all time', value: data.totals.orders },
  ];

  const ordersByStatus = data.orders_by_status
    .map((row) => ({
      ...row,
      name: orderStatusLabel(row.status),
      color: orderStatusColor(row.status),
    }))
    .sort((a, b) => b.count - a.count);
  const totalOrders = ordersByStatus.reduce((sum, row) => sum + row.count, 0);
  const share = (count) => (totalOrders ? Math.round((count / totalOrders) * 100) : 0);

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

      <AIReviewSummaryCard />

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
          <CardHeader className="admin-dashboard-page__month-header">
            <CardTitle>Orders · {monthTitle(month)}</CardTitle>
            <div className="admin-dashboard-page__month-nav">
              <Button
                size="icon"
                variant="outline"
                aria-label="Previous month"
                onClick={() => setMonth((current) => shiftMonth(current, -1))}
              >
                <ChevronLeft className="page-primitive__icon-sm" />
              </Button>
              <select
                className="page-primitive__select admin-dashboard-page__month-select"
                aria-label="Month"
                value={month}
                onChange={(event) => setMonth(event.target.value)}
              >
                {MONTH_NAMES.map((name, index) => (
                  <option
                    key={name}
                    value={`${month.split('-')[0]}-${String(index + 1).padStart(2, '0')}`}
                  >
                    {name}
                  </option>
                ))}
              </select>
              <Button
                size="icon"
                variant="outline"
                aria-label="Next month"
                disabled={month >= currentMonthKey()}
                onClick={() => setMonth((current) => shiftMonth(current, 1))}
              >
                <ChevronRight className="page-primitive__icon-sm" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="page-primitive__chart-h">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={monthQuery.data?.days ?? []}
                margin={{ top: 18, right: 12, bottom: 4 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border)"
                  vertical={false}
                />
                <XAxis
                  dataKey="date"
                  tickFormatter={dayOfMonth}
                  tick={{ fontSize: 12 }}
                  tickMargin={8}
                  minTickGap={18}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  width={28}
                  tick={{ fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  labelFormatter={fullDate}
                  formatter={(value) => [value, 'Orders']}
                  cursor={{ stroke: 'var(--color-border)' }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#15803d"
                  strokeWidth={2.5}
                  dot={{ r: 2.5, fill: '#15803d', strokeWidth: 0 }}
                  activeDot={{ r: 5 }}
                  label={countLabel}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Orders by status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="admin-dashboard-page__donut">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={ordersByStatus}
                    dataKey="count"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius="58%"
                    outerRadius="88%"
                    paddingAngle={1}
                    stroke="none"
                    isAnimationActive={false}
                  >
                    {ordersByStatus.map((entry) => (
                      <Cell key={entry.status} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value, name) => [`${value} (${share(value)}%)`, name]} />
                </PieChart>
              </ResponsiveContainer>
              <div className="admin-dashboard-page__donut-centre">
                <b>{totalOrders}</b>
                <span>orders</span>
              </div>
            </div>
            <ul className="admin-dashboard-page__legend">
              {ordersByStatus.map((row) => (
                <li key={row.status}>
                  <span
                    className="admin-dashboard-page__swatch"
                    style={{ backgroundColor: row.color }}
                  />
                  <span className="admin-dashboard-page__legend-name">{row.name}</span>
                  <b>{row.count}</b>
                  <span className="admin-dashboard-page__legend-share">{share(row.count)}%</span>
                </li>
              ))}
            </ul>
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
