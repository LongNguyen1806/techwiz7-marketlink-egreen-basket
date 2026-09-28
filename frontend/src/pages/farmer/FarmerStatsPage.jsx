import { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { ROUTES } from '../../constants/routes';
import { useUrlFilters } from '../../hooks/common/useUrlFilters';
import {
  STATS_RANGE_DAYS,
  dateRangeError,
  lastDaysRange,
  useFarmerStats,
} from '../../hooks/queries/farmer/useFarmerDashboard';
import { formatDate, formatMoney, moneyToNumber } from '../../utils/formatters';
import { orderStatusLabel, quantityLabel } from '../../utils/labels';
import '../../styles/farmer/FarmerStatsPage.css';

const PRESETS = [7, 30, 90];
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const CHART_COLOR = '#16a34a';

const shortDate = (value) => formatDate(value).slice(0, 5);
const percent = (part, whole) => (whole ? Math.round((part / whole) * 100) : 0);

function sameRange(a, b) {
  return a.from === b.from && a.to === b.to;
}

// Revenue per week, each bar labelled with the Monday it starts on.
function byWeek(days) {
  const weeks = new Map();
  days.forEach((day) => {
    const date = new Date(`${day.date}T00:00:00`);
    date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const week = weeks.get(key) ?? { date: key, revenue: 0, orders: 0 };
    week.revenue += day.revenue;
    week.orders += day.orders;
    weeks.set(key, week);
  });
  return [...weeks.values()];
}

function revenueChange(current, previous) {
  if (previous === 0) return current > 0 ? 'No sales in the period before' : null;
  const change = Math.round(((current - previous) / previous) * 100);
  if (change === 0) return 'Same as the period before';
  return `${change > 0 ? '↑' : '↓'} ${Math.abs(change)}% vs the period before`;
}

function Kpi({ label, value, note, tone }) {
  return (
    <Card>
      <CardHeader className="page-primitive__card-header-tight">
        <CardTitle className="page-primitive__card-title-muted">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="page-primitive__stat-value">{value}</p>
        {note ? <p className={`farmer-stats-page__note${tone ? ` farmer-stats-page__note--${tone}` : ''}`}>{note}</p> : null}
      </CardContent>
    </Card>
  );
}

Kpi.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  note: PropTypes.string,
  tone: PropTypes.oneOf(['up', 'down']),
};

function ShareBar({ label, detail, share }) {
  return (
    <li className="farmer-stats-page__share-row">
      <div className="farmer-stats-page__share-head">
        <span className="page-primitive__font-medium">{label}</span>
        <span className="page-primitive__muted-xs">{detail}</span>
      </div>
      <div className="farmer-stats-page__share-track" aria-hidden>
        <div className="farmer-stats-page__share-fill" style={{ width: `${share}%` }} />
      </div>
    </li>
  );
}

ShareBar.propTypes = {
  label: PropTypes.string.isRequired,
  detail: PropTypes.string.isRequired,
  share: PropTypes.number.isRequired,
};

export default function FarmerStatsPage() {
  const { filters: range, setFilters } = useUrlFilters(lastDaysRange(STATS_RANGE_DAYS));
  const [groupBy, setGroupBy] = useState('day');
  const rangeError = dateRangeError(range);
  const query = useFarmerStats(range);
  const data = query.data;

  const revenueSeries = useMemo(() => {
    if (!data) return [];
    return groupBy === 'week' ? byWeek(data.revenue_by_day) : data.revenue_by_day;
  }, [data, groupBy]);

  const header = (
    <>
      <PageHeader
        title="Stall performance"
        description="How your stall sold over the dates you choose. Figures count orders by their pickup day."
      />
      <div className="farmer-stats-page__range">
        <div className="farmer-stats-page__chips" role="group" aria-label="Period">
          {PRESETS.map((days) => (
            <button
              key={days}
              type="button"
              className={`farmer-stats-page__chip${sameRange(range, lastDaysRange(days)) ? ' is-active' : ''}`}
              onClick={() => setFilters(lastDaysRange(days), { replace: true })}
            >
              Last {days} days
            </button>
          ))}
        </div>
        <div className="farmer-stats-page__dates">
          <Input
            id="from"
            type="date"
            label="From"
            value={range.from}
            max={range.to}
            onChange={(event) => setFilters({ from: event.target.value }, { replace: true })}
          />
          <span className="page-primitive__muted-sm" aria-hidden>
            –
          </span>
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
      {rangeError ? <p className="page-primitive__error">{rangeError}</p> : null}
    </>
  );

  if (!data) {
    return (
      <div className="farmer-stats-page">
        {header}
        {query.isError ? (
          <EmptyState title="Stats couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()} />
        ) : rangeError ? null : (
          <PageSkeleton />
        )}
      </div>
    );
  }

  const { kpis } = data;
  const revenue = moneyToNumber(kpis.revenue);
  const previousRevenue = moneyToNumber(kpis.previous_revenue);
  const change = revenueChange(revenue, previousRevenue);
  const finishedTotal = data.orders_by_status.reduce((sum, row) => sum + row.count, 0);
  const weekdayData = data.orders_by_weekday.map((row) => ({ ...row, day: WEEKDAYS[row.weekday - 1] }));
  const busiest = weekdayData.reduce((best, row) => (row.orders > best.orders ? row : best), weekdayData[0]);

  return (
    <div className="farmer-stats-page" aria-busy={query.isFetching}>
      {header}

      <div className="page-primitive__grid-stats-4">
        <Kpi
          label="Revenue"
          value={formatMoney(kpis.revenue)}
          note={change ?? undefined}
          tone={revenue > previousRevenue ? 'up' : revenue < previousRevenue ? 'down' : undefined}
        />
        <Kpi label="Total orders" value={kpis.total_orders} note="Every order picked up in this period" />
        <Kpi label="Completed" value={kpis.completed_orders} note="Picked up and paid" />
        <Kpi
          label="Completion rate"
          value={kpis.finished_orders ? `${percent(kpis.completed_orders, kpis.finished_orders)}%` : '—'}
          note={`${kpis.completed_orders} of ${kpis.finished_orders} finished orders`}
        />
        <Kpi label="Average order" value={formatMoney(kpis.average_order_value)} note="Per completed order" />
        <Kpi label="Customers" value={kpis.customers} note="Who picked up at least one order" />
        <Kpi
          label="Returning customers"
          value={kpis.returning_customers}
          note={kpis.customers ? `${percent(kpis.returning_customers, kpis.customers)}% bought 2 times or more` : 'No customers yet'}
        />
        <Kpi
          label="Average rating"
          value={kpis.rating.average === null ? '—' : `${kpis.rating.average} ★`}
          note={`${kpis.rating.count} review${kpis.rating.count === 1 ? '' : 's'}`}
        />
      </div>

      <Card>
        <CardHeader className="page-primitive__card-header-row">
          <CardTitle>Revenue summary</CardTitle>
          <div className="farmer-stats-page__chips" role="group" aria-label="Group revenue by">
            {['day', 'week'].map((value) => (
              <button
                key={value}
                type="button"
                className={`farmer-stats-page__chip${groupBy === value ? ' is-active' : ''}`}
                onClick={() => setGroupBy(value)}
              >
                By {value}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent className="page-primitive__chart-h-72">
          {revenue === 0 ? (
            <p className="page-primitive__muted-sm">No completed orders in this period.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={revenueSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={shortDate} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(value) => formatMoney(value)} width={64} />
                <Tooltip
                  labelFormatter={(label) => (groupBy === 'week' ? `Week of ${formatDate(label)}` : formatDate(label))}
                  formatter={(value, name) => (name === 'revenue' ? [formatMoney(value), 'Revenue'] : [value, 'Orders'])}
                />
                <Bar dataKey="revenue" fill={CHART_COLOR} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <div className="farmer-stats-page__two-col">
        <Card>
          <CardHeader>
            <CardTitle>How orders ended</CardTitle>
          </CardHeader>
          <CardContent>
            {finishedTotal === 0 ? (
              <p className="page-primitive__muted-sm">No finished orders in this period.</p>
            ) : (
              <ul className="farmer-stats-page__share-list page-primitive__list-plain">
                {data.orders_by_status.map((row) => (
                  <ShareBar
                    key={row.status}
                    label={orderStatusLabel(row.status)}
                    detail={`${row.count} · ${percent(row.count, finishedTotal)}%`}
                    share={percent(row.count, finishedTotal)}
                  />
                ))}
              </ul>
            )}
            {data.open_orders > 0 ? (
              <p className="page-primitive__muted-xs farmer-stats-page__footnote">
                {data.open_orders} order{data.open_orders === 1 ? ' is' : 's are'} still open and not counted here.
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Busiest pickup days</CardTitle>
          </CardHeader>
          <CardContent className="page-primitive__chart-h">
            {kpis.total_orders === 0 ? (
              <p className="page-primitive__muted-sm">No orders in this period.</p>
            ) : (
              <>
                <p className="page-primitive__muted-xs">
                  Most orders are picked up on {busiest.day}. Bring more produce that day.
                </p>
                <ResponsiveContainer width="100%" height="90%">
                  <BarChart data={weekdayData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} allowDecimals={false} width={32} />
                    <Tooltip formatter={(value) => [value, 'Orders']} />
                    <Bar dataKey="orders" fill={CHART_COLOR} radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Best-selling produce</CardTitle>
        </CardHeader>
        <CardContent>
          {data.top_products.length === 0 ? (
            <p className="page-primitive__muted-sm">No sales in this period yet.</p>
          ) : (
            <div className="page-primitive__table-wrap">
              <table className="page-primitive__table">
                <thead className="page-primitive__table-head">
                  <tr>
                    <th className="page-primitive__table-th">#</th>
                    <th className="page-primitive__table-th">Product</th>
                    <th className="page-primitive__table-th">Sold</th>
                    <th className="page-primitive__table-th">Orders</th>
                    <th className="page-primitive__table-th">Revenue</th>
                    <th className="page-primitive__table-th">Share of revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_products.map((product, index) => (
                    <tr key={`${product.product_id}-${product.unit}`} className="page-primitive__table-row">
                      <td className="page-primitive__table-td">{index + 1}</td>
                      <td className="page-primitive__table-td page-primitive__font-medium">{product.name}</td>
                      <td className="page-primitive__table-td">
                        {quantityLabel(product.quantity_sold, product.unit)}
                      </td>
                      <td className="page-primitive__table-td">{product.orders}</td>
                      <td className="page-primitive__table-td">{formatMoney(product.revenue)}</td>
                      <td className="page-primitive__table-td">{percent(product.revenue, revenue)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sales by market</CardTitle>
        </CardHeader>
        <CardContent>
          {data.sales_by_market.length === 0 ? (
            <p className="page-primitive__muted-sm">No sales in this period yet.</p>
          ) : (
            <ul className="farmer-stats-page__share-list page-primitive__list-plain">
              {data.sales_by_market.map((market) => (
                <ShareBar
                  key={market.market_id}
                  label={market.name}
                  detail={`${formatMoney(market.revenue)} · ${market.orders} order${market.orders === 1 ? '' : 's'} · ${percent(market.revenue, revenue)}%`}
                  share={percent(market.revenue, revenue)}
                />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <p className="page-primitive__muted-sm">
        Looking for a single order?{' '}
        <Link className="page-primitive__link-underline" to={`${ROUTES.FARMER.ORDERS}?tab=history`}>
          See every past order in Orders → History
        </Link>
      </p>
    </div>
  );
}
