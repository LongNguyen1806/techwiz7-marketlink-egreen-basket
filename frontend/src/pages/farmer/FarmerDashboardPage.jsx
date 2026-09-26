import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, Package, TrendingUp, Wallet } from 'lucide-react';
import { useFarmerDashboard } from '../../features/farmer/hooks/useFarmerDashboard';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Button } from '../../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { useAuth } from '../../features/auth/hooks/useAuth';
import { formatDate, formatVnd } from '../../utils/formatters';
import '../../styles/farmer/FarmerDashboardPage.css';
function defaultRange() {
    const to = new Date();
    const from = new Date();
    from.setDate(from.getDate() - 14);
    return {
        from: from.toISOString().slice(0, 10),
        to: to.toISOString().slice(0, 10),
    };
}
export default function FarmerDashboardPage() {
    const { user } = useAuth();
    const initial = useMemo(() => defaultRange(), []);
    const [from, setFrom] = useState(initial.from);
    const [to, setTo] = useState(initial.to);
    const query = useFarmerDashboard({ from, to });
    if (query.isLoading)
        return <PageSkeleton />;
    if (query.isError || !query.data) {
        return (<EmptyState title="Overview couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()}/>);
    }
    const data = query.data;
    const kpis = [
        {
            label: 'Total orders',
            value: String(data.kpis.total_orders),
            icon: Package,
        },
        {
            label: 'Pending approval',
            value: String(data.kpis.pending_approval),
            icon: AlertTriangle,
        },
        {
            label: 'In progress',
            value: String(data.kpis.in_progress),
            icon: TrendingUp,
        },
        {
            label: 'Revenue',
            value: formatVnd(data.kpis.revenue),
            icon: Wallet,
        },
    ];
    return (<div className="farmer-dashboard-page">
      <PageHeader title="Stall overview" description={`${user?.display_name ?? 'Your stall'} â€” today's pickups, revenue, and what needs attention.`} actions={<div className="page-primitive__inline-row-end">
            <div>
              <Input id="from" type="date" label="From" value={from} onChange={(e) => setFrom(e.target.value)}/>
            </div>
            <div>
              <Input id="to" type="date" label="To" value={to} onChange={(e) => setTo(e.target.value)}/>
            </div>
          </div>}/>

      {data.overdue_open_count > 0 ? (<div className="farmer-dashboard-page__overdue">
          <p className="page-primitive__font-medium">
            {data.overdue_open_count} overdue order(s) need attention
          </p>
          <Button asChild size="sm" variant="outline">
            <Link to="/farmer/orders?tab=overdue">View now</Link>
          </Button>
        </div>) : null}

      <div className="page-primitive__grid-stats-4">
        {kpis.map((item) => (<Card key={item.label}>
            <CardHeader className="page-primitive__card-header-row page-primitive__card-header-tight">
              <CardTitle className="page-primitive__card-title-muted">
                {item.label}
              </CardTitle>
              <item.icon className="page-primitive__kpi-icon"/>
            </CardHeader>
            <CardContent>
              <p className="page-primitive__stat-value">{item.value}</p>
            </CardContent>
          </Card>))}
      </div>

      <div className="farmer-dashboard-page__charts">
        <Card>
          <CardHeader>
            <CardTitle>Daily revenue</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__chart-h">
            {data.revenue_by_day.length === 0 ? (<p className="page-primitive__muted-sm">No revenue in this period.</p>) : (<ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.revenue_by_day}>
                  <defs>
                    <linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#16a34a" stopOpacity={0.35}/>
                      <stop offset="100%" stopColor="#16a34a" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)"/>
                  <XAxis dataKey="date" tick={{ fontSize: 11 }}/>
                  <YAxis tick={{ fontSize: 11 }} width={56}/>
                  <Tooltip formatter={(value) => formatVnd(Number(value))} labelFormatter={(label) => formatDate(String(label))}/>
                  <Area type="monotone" dataKey="revenue" stroke="#15803d" fill="url(#revFill)" strokeWidth={2}/>
                </AreaChart>
              </ResponsiveContainer>)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Best sellers</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__chart-h">
            {data.top_products.length === 0 ? (<p className="page-primitive__muted-sm">No data yet.</p>) : (<ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.top_products} layout="vertical" margin={{ left: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)"/>
                  <XAxis type="number" hide/>
                  <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }}/>
                  <Tooltip formatter={(value) => formatVnd(Number(value))}/>
                  <Bar dataKey="quantity_sold" fill="#ca8a04" radius={[0, 8, 8, 0]}/>
                </BarChart>
              </ResponsiveContainer>)}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="page-primitive__card-header-row">
          <CardTitle>Upcoming pickups</CardTitle>
          <Button asChild variant="link" size="sm">
            <Link to="/farmer/orders">All orders</Link>
          </Button>
        </CardHeader>
        <CardContent className="farmer-dashboard-page__upcoming-list">
          {data.upcoming.length === 0 ? (<p className="page-primitive__muted-sm">No upcoming orders.</p>) : (data.upcoming.map((order) => (<div key={order.id} className="page-primitive__row-card-responsive">
                <div>
                  <Link to={`/farmer/orders/${order.id}`} className="page-primitive__semibold page-primitive__link-underline">
                    #{order.id} Â· {order.customer.full_name}
                  </Link>
                  <p className="page-primitive__muted-sm">
                    {order.market.name} Â· {formatDate(order.pickup_date)} Â·{' '}
                    {order.item_count} items Â· {formatVnd(order.total_amount)}
                  </p>
                </div>
                <div className="page-primitive__actions-row">
                  <StatusBadge status={order.status}/>
                </div>
              </div>)))}
        </CardContent>
      </Card>
    </div>);
}

