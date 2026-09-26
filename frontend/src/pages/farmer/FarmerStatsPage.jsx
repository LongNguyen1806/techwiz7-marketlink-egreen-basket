import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { STATS_RANGE_DAYS, useFarmerStats } from '../../hooks/queries/farmer/useFarmerDashboard';
import { formatDate, formatMoney } from '../../utils/formatters';
import '../../styles/farmer/FarmerStatsPage.css';

export default function FarmerStatsPage() {
  const query = useFarmerStats();

  if (query.isPending) return <PageSkeleton />;
  if (!query.data) {
    return <EmptyState title="Stats couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />;
  }

  const data = query.data;
  
  const byRevenue = [...data.top_products].sort((a, b) => b.revenue - a.revenue);
  const period = `${formatDate(data.range.from)} – ${formatDate(data.range.to)}`;

  return (
    <div className="farmer-stats-page">
      <PageHeader
        title="Stall performance"
        description={`Last ${STATS_RANGE_DAYS} days (${period}): revenue trends and your best-selling produce.`}
      />
      <div className="page-primitive__stat-grid-3">
        <Card>
          <CardHeader className="page-primitive__card-header-tight">
            <CardTitle className="page-primitive__card-title-muted">Revenue</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__stat-value">{formatMoney(data.kpis.revenue)}</CardContent>
        </Card>
        <Card>
          <CardHeader className="page-primitive__card-header-tight">
            <CardTitle className="page-primitive__card-title-muted">Total orders</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__stat-value">{data.kpis.total_orders}</CardContent>
        </Card>
        <Card>
          <CardHeader className="page-primitive__card-header-tight">
            <CardTitle className="page-primitive__card-title-muted">In progress</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__stat-value">{data.kpis.in_progress}</CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top produce by revenue</CardTitle>
        </CardHeader>
        <CardContent className="page-primitive__chart-h-72">
          {byRevenue.length === 0 ? (
            <p className="page-primitive__muted-sm">No sales in this period yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={byRevenue}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(value) => formatMoney(value)} width={64} />
                <Tooltip formatter={(value) => [formatMoney(value), 'Revenue']} />
                <Bar dataKey="revenue" fill="#16a34a" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
