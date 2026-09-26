import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useFarmerStats } from '../../features/farmer/hooks/useFarmerStats';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { formatVnd } from '../../utils/formatters';
import '../../styles/farmer/FarmerStatsPage.css';
export default function FarmerStatsPage() {
    const query = useFarmerStats();
    if (query.isLoading)
        return <PageSkeleton />;
    if (query.isError || !query.data) {
        return (<EmptyState title="Stats couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()}/>);
    }
    const data = query.data;
    return (<div className="farmer-stats-page">
      <PageHeader title="Stall performance" description="Revenue trends and your best-selling produce."/>
      <div className="page-primitive__stat-grid-3">
        <Card>
          <CardHeader className="page-primitive__card-header-tight">
            <CardTitle className="page-primitive__card-title-muted">Revenue</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__stat-value">
            {formatVnd(data.kpis.revenue)}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="page-primitive__card-header-tight">
            <CardTitle className="page-primitive__card-title-muted">Total orders</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__stat-value">
            {data.kpis.total_orders}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="page-primitive__card-header-tight">
            <CardTitle className="page-primitive__card-title-muted">In progress</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__stat-value">
            {data.kpis.in_progress}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top produce by revenue</CardTitle>
        </CardHeader>
        <CardContent className="page-primitive__chart-h-72">
          {data.top_products.length === 0 ? (<p className="page-primitive__muted-sm">No data yet.</p>) : (<ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.top_products}>
                <CartesianGrid strokeDasharray="3 3"/>
                <XAxis dataKey="name" tick={{ fontSize: 11 }}/>
                <YAxis tick={{ fontSize: 11 }}/>
                <Tooltip formatter={(v) => formatVnd(Number(v))}/>
                <Bar dataKey="revenue" fill="#16a34a" radius={[8, 8, 0, 0]}/>
              </BarChart>
            </ResponsiveContainer>)}
        </CardContent>
      </Card>
    </div>);
}

