import { useQuery } from '@tanstack/react-query';

import { adminApi } from '@/api/admin/adminApi';
import { QUERY_KEYS } from '@/config/constants';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';

import './AdminSettingsPage.css';

const LIMITS = [
  {
    key: 'booking_horizon_days',
    label: 'How far ahead a shopper may book',
    unit: 'days',
    note: 'Also decides which market and stall closures count as upcoming.',
  },
  {
    key: 'max_placed_orders_per_customer',
    label: 'Orders one shopper may have awaiting approval',
    unit: 'orders',
    note: 'Stops a single account reserving a stall’s whole stock.',
  },
  {
    key: 'at_risk_threshold',
    label: 'No-shows before a shopper is flagged',
    unit: 'no-shows',
    note: 'Only missed collections count. An expired order is nobody’s fault.',
  },
  {
    key: 'at_risk_window_days',
    label: 'Period those no-shows are counted over',
    unit: 'days',
    note: 'A rolling window, so an old no-show stops counting.',
  },
  {
    key: 'max_upload_mb',
    label: 'Largest image a stall may upload',
    unit: 'MB',
    note: 'Applies to stall photos, market photos and product photos.',
  },
];

export default function AdminSettingsPage() {
  const query = useQuery({
    queryKey: QUERY_KEYS.ADMIN_SETTINGS,
    queryFn: adminApi.getSettings,
  });

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError || !query.data) {
    return (
      <EmptyState
        title="Settings could not be loaded"
        actionLabel="Try again"
        onAction={() => query.refetch()}
      />
    );
  }

  return (
    <div className="admin-settings-page">
      <PageHeader
        title="Platform limits"
        description="What the platform is enforcing right now. These are set when the app is deployed, so they are shown here rather than edited."
      />

      <dl className="admin-settings-page__list">
        {LIMITS.map((limit) => (
          <div key={limit.key} className="admin-settings-page__row">
            <dt>
              {limit.label}
              <span className="admin-settings-page__note">{limit.note}</span>
            </dt>
            <dd>
              <b>{query.data[limit.key]}</b> {limit.unit}
            </dd>
          </div>
        ))}
      </dl>

      <p className="page-primitive__muted-sm">
        To change one of these, set the matching environment variable and deploy again.
      </p>
    </div>
  );
}
