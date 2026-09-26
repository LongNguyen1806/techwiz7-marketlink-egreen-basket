import { Link } from 'react-router-dom';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, Package, TrendingUp, Wallet } from 'lucide-react';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Button } from '../../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { ROUTES } from '../../constants/routes';
import { useAuth } from '../../hooks/authentication/useAuth';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import {
  DASHBOARD_DEFAULT_DAYS,
  dateRangeError,
  lastDaysRange,
  useFarmerDashboard,
} from '../../hooks/queries/farmer/useFarmerDashboard';
import { formatDate, formatMoney, formatPickupWindow } from '../../utils/formatters';
import '../../styles/farmer/FarmerDashboardPage.css';

const shortDate = (value) => formatDate(value).slice(0, 5);

export default function FarmerDashboardPage() {
  const { user } = useAuth();
  const { filters: range, setFilters } = useUrlFilters(lastDaysRange(DASHBOARD_DEFAULT_DAYS));
  const rangeError = dateRangeError(range);
  const query = useFarmerDashboard(range);

  const rangeInputs = (
    <div className="page-primitive__inline-row-end">
      <div>
        <Input
          id="from"
          type="date"
          label="From"
          value={range.from}
          max={range.to}
          onChange={(event) => setFilters({ from: event.target.value }, { replace: true })}
        />
      </div>
      <div>
        <Input
          id="to"
          type="date"
          label="To"
          value={range.to}
          min={range.from}
          onChange={(event) => setFilters({ to: event.target.value }, { replace: true })}
        />
      </div>
    </div>
  );

  const header = (
    <PageHeader
      title="Stall overview"
      description={`${user?.display_name ?? 'Your stall'} — today's pickups, revenue, and what needs attention.`}
      actions={rangeInputs}
    />
  );

  if (!query.data) {
    if (query.isError) {
      return (
        <div className="farmer-dashboard-page">
          {header}
          <EmptyState title="Overview couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />
        </div>
      );
    }
    return rangeError ? (
      <div className="farmer-dashboard-page">
        {header}
        <p className="page-primitive__error">{rangeError}</p>
      </div>
    ) : (
      <PageSkeleton />
    );
  }

  const data = query.data;
  const hasRevenue = data.revenue_by_day.some((day) => day.revenue > 0);
  const kpis = [
    { label: 'Total orders', value: String(data.kpis.total_orders), icon: Package },
    { label: 'Pending approval', value: String(data.kpis.pending_approval), icon: AlertTriangle },
    { label: 'In progress', value: String(data.kpis.in_progress), icon: TrendingUp },
    { label: 'Revenue', value: formatMoney(data.kpis.revenue), icon: Wallet },
  ];

  return (
    <div className="farmer-dashboard-page" aria-busy={query.isFetching}>
      {header}
      {rangeError ? <p className="page-primitive__error">{rangeError}</p> : null}

      {data.overdue_open_count > 0 ? (
        <div className="farmer-dashboard-page__overdue">
          <p className="page-primitive__font-medium">
            {data.overdue_open_count} overdue order{data.overdue_open_count === 1 ? '' : 's'} need
            {data.overdue_open_count === 1 ? 's' : ''} attention
          </p>
          <Button asChild size="sm" variant="outline">
            <Link to={`${ROUTES.FARMER.ORDERS}?tab=overdue`}>View now</Link>
          </Button>
        </div>
      ) : null}

      <div className="page-primitive__grid-stats-4">
        {kpis.map((item) => (
          <Card key={item.label}>
            <CardHeader className="page-primitive__card-header-row page-primitive__card-header-tight">
              <CardTitle className="page-primitive__card-title-muted">{item.label}</CardTitle>
              <item.icon className="page-primitive__kpi-icon" />
            </CardHeader>
            <CardContent>
              <p className="page-primitive__stat-value">{item.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="farmer-dashboard-page__charts">
        <Card>
          <CardHeader>
            <CardTitle>Daily revenue</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__chart-h">
            {!hasRevenue ? (
              <p className="page-primitive__muted-sm">No revenue in this period.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.revenue_by_day}>
                  <defs>
                    <linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#16a34a" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#16a34a" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={shortDate} />
                  <YAxis tick={{ fontSize: 11 }} width={56} tickFormatter={(value) => formatMoney(value)} />
                  <Tooltip
                    formatter={(value) => [formatMoney(value), 'Revenue']}
                    labelFormatter={(label) => formatDate(String(label))}
                  />
                  <Area type="monotone" dataKey="revenue" stroke="#15803d" fill="url(#revFill)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Best sellers</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__chart-h">
            {data.top_products.length === 0 ? (
              <p className="page-primitive__muted-sm">No data yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.top_products} layout="vertical" margin={{ left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis type="number" hide allowDecimals={false} />
                  <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(value) => [value, 'Sold']} />
                  <Bar dataKey="quantity_sold" fill="#ca8a04" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="page-primitive__card-header-row">
          <CardTitle>Upcoming pickups</CardTitle>
          <Button asChild variant="link" size="sm">
            <Link to={ROUTES.FARMER.ORDERS}>All orders</Link>
          </Button>
        </CardHeader>
        <CardContent className="farmer-dashboard-page__upcoming-list">
          {data.upcoming.length === 0 ? (
            <p className="page-primitive__muted-sm">No upcoming orders.</p>
          ) : (
            data.upcoming.map((order) => (
              <div key={order.id} className="page-primitive__row-card-responsive">
                <div>
                  <Link
                    to={ROUTES.FARMER.ORDER(order.id)}
                    className="page-primitive__semibold page-primitive__link-underline"
                  >
                    #{order.id} · {order.customer.full_name}
                  </Link>
                  <p className="page-primitive__muted-sm">
                    {order.market.name} · {formatPickupWindow(order.pickup_start_at, order.pickup_end_at)} ·{' '}
                    {order.item_count} item{order.item_count === 1 ? '' : 's'} · {formatMoney(order.total_amount)}
                  </p>
                </div>
                <div className="page-primitive__actions-row">
                  <StatusBadge status={order.status} />
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
