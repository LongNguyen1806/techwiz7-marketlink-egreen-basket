import { useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { toast } from 'sonner';

import { ApiError } from '@/lib/ApiError';
import {
  exportAdminReports,
  useAdminReports,
} from '../../hooks/queries/admin/useAdminReports';
import { useAdminMarkets } from '../../hooks/queries/admin/useAdminMarkets';
import { EmptyState } from '@/components/common/feedback/EmptyState';
import { PageHeader } from '@/components/common/layout/PageHeader';
import { PageSkeleton } from '@/components/common/feedback/PageSkeleton';
import { Button } from '@/components/common/forms/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/common/cards/Card';
import { Input } from '@/components/common/forms/Input';
import { Label } from '@/components/common/forms/Label';
import { formatVnd } from '@/utils/formatters';
import { orderStatusLabel } from '@/utils/labels';
import { orderStatusColor } from '@/utils/statusColors';

import '@/components/common/table/FilterBar.css';
import './AdminReportsPage.css';

function defaultRange() {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - 30);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}

// A full dong figure at the end of a bar is a dozen characters wide and pushes the plot area
// to nothing. The tooltip still gives the exact number.
function compactVnd(value) {
  const amount = Number(value) || 0;
  if (amount >= 1_000_000_000) return `${(amount / 1_000_000_000).toFixed(1)} tỷ`;
  if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(1)} tr`;
  if (amount >= 1_000) return `${Math.round(amount / 1_000)} k`;
  return String(Math.round(amount));
}

export default function AdminReportsPage() {
  const initial = useMemo(() => defaultRange(), []);
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [marketId, setMarketId] = useState('');
  const [applied, setApplied] = useState({
    ...initial,
    market_id: undefined,
  });
  const [exporting, setExporting] = useState(false);

  const marketsQuery = useAdminMarkets();
  const reportQuery = useAdminReports(applied);

  // Both charts want the biggest bar at the top, and revenue arrives as a decimal string
  // that a chart axis cannot measure.
  const report = reportQuery.data;
  const ordersByStatus = useMemo(
    () =>
      (report?.orders_by_status ?? [])
        .map((row) => ({ ...row, name: orderStatusLabel(row.status) }))
        .sort((a, b) => b.count - a.count),
    [report],
  );
  const revenueByMarket = useMemo(
    () =>
      (report?.revenue_by_market ?? [])
        .map((row) => ({ ...row, revenue: Number(row.revenue) || 0 }))
        .sort((a, b) => b.revenue - a.revenue),
    [report],
  );

  const daysDiff = () => {
    const a = new Date(from);
    const b = new Date(to);
    return Math.ceil((b.getTime() - a.getTime()) / 86400000);
  };

  const onApply = () => {
    if (daysDiff() > 366) {
      toast.error('Date range cannot exceed 366 days');
      return;
    }
    if (daysDiff() < 0) {
      toast.error('End date must be after start date');
      return;
    }
    setApplied({
      from,
      to,
      market_id: marketId ? Number(marketId) : undefined,
    });
  };

  const onExport = async () => {
    setExporting(true);
    try {
      const blob = await exportAdminReports({
        from: applied.from,
        to: applied.to,
        market_id: applied.market_id,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'marketlink-report.xlsx';
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Report exported');
    } catch (e) {
      toast.error(ApiError.fromUnknown(e).friendlyMessage);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="admin-reports-page">
      <PageHeader
        title="Reports"
        description="Order volume, revenue by market, and top-performing stalls."
        actions={
          <Button variant="outline" loading={exporting} onClick={() => void onExport()}>
            Export Excel
          </Button>
        }
      />

      <div className="page-primitive__filters-bar">
        <div>
          <Input
            type="date"
            label="From"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div>
          <Input
            type="date"
            label="To"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
        <div>
          <Label className="page-primitive__label-xs">Market</Label>
          <select
            className="page-primitive__select"
            value={marketId}
            onChange={(e) => setMarketId(e.target.value)}
          >
            <option value="">All markets</option>
            {marketsQuery.data?.results.map((m) => (
              <option key={m.id} value={String(m.id)}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
        <Button onClick={onApply}>Apply</Button>
        {/* Every filter row in the admin ends with this button, enabled or not, so an admin
            learns one place to look rather than one per screen. Here "clear" means the
            default range, because a report with no dates at all is not a report. */}
        <Button
          variant="ghost"
          className="filter-bar__clear"
          disabled={from === initial.from && to === initial.to && !marketId}
          onClick={() => {
            setFrom(initial.from);
            setTo(initial.to);
            setMarketId('');
            setApplied({ ...initial, market_id: undefined });
          }}
        >
          Clear
        </Button>
      </div>

      {reportQuery.isLoading ? (
        <PageSkeleton />
      ) : reportQuery.isError || !reportQuery.data ? (
        <EmptyState
          title="Report couldn't be loaded"
          actionLabel="Try again"
          onAction={() => reportQuery.refetch()}
        />
      ) : (
        <>
          <div className="page-primitive__grid-2-lg">
            <Card>
              <CardHeader>
                <CardTitle>Orders by status</CardTitle>
              </CardHeader>
              <CardContent className="page-primitive__chart-card-body">
                <ResponsiveContainer width="100%" height="100%">
                  {/* Bars run sideways: eight status names along the bottom either overlap
                      or have to be tilted, and neither reads well. */}
                  <BarChart
                    layout="vertical"
                    data={ordersByStatus}
                    margin={{ left: 4, right: 40, top: 4, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} hide />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={124}
                      tick={{ fontSize: 12 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip formatter={(value) => [value, 'Orders']} cursor={false} />
                    <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
                      {ordersByStatus.map((row) => (
                        <Cell key={row.status} fill={orderStatusColor(row.status)} />
                      ))}
                      <LabelList
                        dataKey="count"
                        position="right"
                        style={{ fontSize: 12, fontWeight: 600 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Revenue by market</CardTitle>
              </CardHeader>
              <CardContent className="page-primitive__chart-card-body">
                <ResponsiveContainer width="100%" height="100%">
                  {/* Same reasoning, plus market names are longer than status names and the
                      money labels need room at the end of each bar. */}
                  <BarChart
                    layout="vertical"
                    data={revenueByMarket}
                    margin={{ left: 4, right: 68, top: 4, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 12 }} hide />
                    <YAxis
                      type="category"
                      dataKey="market_name"
                      width={124}
                      tick={{ fontSize: 12 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      formatter={(value) => [formatVnd(Number(value)), 'Revenue']}
                      cursor={false}
                    />
                    <Bar dataKey="revenue" fill="#ca8a04" radius={[0, 6, 6, 0]} barSize={16}>
                      <LabelList
                        dataKey="revenue"
                        position="right"
                        formatter={compactVnd}
                        style={{ fontSize: 12, fontWeight: 600 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          <div className="page-primitive__table-wrap">
            <table className="page-primitive__table">
              <thead className="page-primitive__table-head">
                <tr>
                  <th className="page-primitive__table-th">Top farmers</th>
                  <th className="page-primitive__table-th">Orders</th>
                  <th className="page-primitive__table-th">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {reportQuery.data.top_farmers.map((f) => (
                  <tr key={f.farmer_id} className="page-primitive__table-row">
                    <td className="page-primitive__table-td page-primitive__font-medium">
                      {f.stall_name}
                    </td>
                    <td className="page-primitive__table-td">{f.completed_orders}</td>
                    <td className="page-primitive__table-td">{formatVnd(f.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
