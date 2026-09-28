import { useState } from 'react';
import { Link } from 'react-router-dom';

import {
  useAdminMarkets,
  useToggleAdminMarket,
} from '../../hooks/queries/admin/useAdminMarkets';
import { EmptyState } from '../../components/feedback/EmptyState';
import { FilterBar } from '../../components/common/table/FilterBar';
import { Input } from '../../components/ui/Input';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { SortSelect } from '../../components/common/SortSelect';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { Textarea } from '../../components/ui/Textarea';
import '../../styles/admin/AdminMarketsPage.css';

const REASON_MIN_LENGTH = 5;

const MARKET_FILTERS = [
  { name: 'q', label: 'Search name or address', type: 'search' },
  {
    name: 'is_active',
    label: 'State',
    type: 'select',
    allLabel: 'Open and closed',
    options: [
      { value: 'true', label: 'Open' },
      { value: 'false', label: 'Closed' },
    ],
  },
];
const CONFIRM_WORD = 'confirm';

const SORT_OPTIONS = [
  { value: 'name', label: 'Name A–Z' },
  { value: '-name', label: 'Name Z–A' },
  { value: '-farmer_count', label: 'Most stalls' },
  { value: '-open_order_count', label: 'Most open orders' },
  { value: '-is_active', label: 'Active first' },
];

export default function AdminMarketsPage() {
  const [ordering, setOrdering] = useState(undefined);
  const [closing, setClosing] = useState(null);
  const [reason, setReason] = useState('');
  const [farmerMessage, setFarmerMessage] = useState('');
  const [typed, setTyped] = useState('');
  const [filters, setFilters] = useState({});
  const query = useAdminMarkets({ ...filters, ordering });
  const toggle = useToggleAdminMarket();

  return (
    <div className="admin-markets-page">
      <PageHeader
        title="Markets"
        description="Create market sessions, edit details, and toggle availability."
        actions={
          <Button asChild>
            <Link to="/admin/markets/new">Add a market</Link>
          </Button>
        }
      />

      <FilterBar
        fields={MARKET_FILTERS}
        value={filters}
        onChange={setFilters}
        onReset={() => setFilters({})}
      />

      <SortSelect
        id="market-sort"
        options={SORT_OPTIONS}
        value={ordering}
        onChange={setOrdering}
      />

      {query.isLoading ? (
        <PageSkeleton />
      ) : !query.data?.results?.length ? (
        <EmptyState
          title="No markets yet"
          description="Add your first market so stalls and shoppers have a place to meet."
        />
      ) : (
        <div className="admin-markets-page__grid">
          {query.data.results.map((m) => (
            <div key={m.id} className="admin-markets-page__card">
              <div className="admin-markets-page__card-head">
                <div>
                  <Link
                    to={`/admin/markets/${m.id}`}
                    className="admin-markets-page__link"
                  >
                    {m.name}
                  </Link>
                  <p className="admin-markets-page__address">{m.address}</p>
                </div>
                <Badge variant={m.is_active ? 'success' : 'secondary'}>
                  {m.is_active ? 'Active' : 'Inactive'}
                </Badge>
              </div>
              <p className="admin-markets-page__meta">
                {m.open_time}–{m.close_time} · {m.farmer_count} stalls
              </p>
              <div className="admin-markets-page__actions">
                <Button asChild size="sm" variant="outline">
                  <Link to={`/admin/markets/${m.id}/edit`}>Edit</Link>
                </Button>
                <Button
                  size="sm"
                  variant={m.is_active ? 'destructive' : 'default'}
                  loading={toggle.isPending}
                  onClick={() => {
                    if (!m.is_active) {
                      toggle.mutate({ id: m.id, active: true });
                      return;
                    }
                    setClosing(m);
                    setReason('');
                  }}
                >
                  {m.is_active ? 'Close' : 'Reopen'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={Boolean(closing)}
        onOpenChange={(open) => {
          if (!open) setClosing(null);
        }}
        title={`Close ${closing?.name ?? 'this market'}?`}
        description={
          'Every order still open at this market will be cancelled and the stock returned. ' +
          'Pickup slots here are switched off until the market reopens; the stalls keep trading at their other markets.'
        }
        confirmLabel="Close market"
        destructive
        loading={toggle.isPending}
        confirmDisabled={
          typed.trim().toLowerCase() !== CONFIRM_WORD ||
          reason.trim().length < REASON_MIN_LENGTH
        }
        onConfirm={() => {
          if (!closing) return;
          toggle.mutate(
            { id: closing.id, active: false, reason, farmerMessage },
            { onSuccess: () => setClosing(null) },
          );
        }}
      >
        <Textarea
          className="admin-markets-page__reason"
          placeholder="Why is it closing? Shoppers and stalls are told this."
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
        {reason.trim().length > 0 && reason.trim().length < REASON_MIN_LENGTH ? (
          <p className="page-primitive__error">
            Please give at least {REASON_MIN_LENGTH} characters.
          </p>
        ) : null}

        <Textarea
          className="admin-markets-page__reason"
          placeholder="Anything else the stalls should know? Emailed to them only. Optional."
          value={farmerMessage}
          onChange={(event) => setFarmerMessage(event.target.value)}
        />

        <div className="admin-markets-page__confirm">
          <Input
            label={`Type ${CONFIRM_WORD} to close this market`}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}
