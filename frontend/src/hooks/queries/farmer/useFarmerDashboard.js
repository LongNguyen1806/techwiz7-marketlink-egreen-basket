import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';
import { moneyToNumber, toApiDate } from '../../../utils/formatters';

const DAY_MS = 24 * 60 * 60 * 1000;
export const MAX_RANGE_DAYS = 366;
export const DASHBOARD_DEFAULT_DAYS = 7;
export const STATS_RANGE_DAYS = 30;


export function lastDaysRange(days) {
  const now = Date.now();
  return { from: toApiDate(new Date(now - (days - 1) * DAY_MS)), to: toApiDate(new Date(now)) };
}


export function dateRangeError({ from, to }) {
  if (!from || !to) return 'Choose both dates';
  if (from > to) return 'The start date must be on or before the end date';
  const days = Math.round((Date.parse(to) - Date.parse(from)) / DAY_MS) + 1;
  if (days > MAX_RANGE_DAYS) return `The range can be at most ${MAX_RANGE_DAYS} days`;
  return null;
}


const toChartData = (data) => ({
  ...data,
  revenue_by_day: data.revenue_by_day.map((day) => ({ ...day, revenue: moneyToNumber(day.revenue) })),
  top_products: data.top_products.map((product) => ({ ...product, revenue: moneyToNumber(product.revenue) })),
});

function useDashboardQuery(range, { staleTime, enabled = true }) {
  return useQuery({
    queryKey: farmerKeys.dashboard.range(range),
    queryFn: ({ signal }) => farmerApi.getDashboard(range, { signal }),
    select: toChartData,
    placeholderData: keepPreviousData,
    staleTime,
    enabled,
  });
}


export function useFarmerDashboard(range) {
  return useDashboardQuery(range, { staleTime: STALE.SHORT, enabled: !dateRangeError(range) });
}


export function useFarmerStats() {
  return useDashboardQuery(lastDaysRange(STATS_RANGE_DAYS), { staleTime: STALE.MINUTE });
}
