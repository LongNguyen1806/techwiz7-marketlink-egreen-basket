import PropTypes from 'prop-types';
import { Search, X } from 'lucide-react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Label } from '../ui/Label';
import { formatDate, toApiDate } from '../../utils/formatters';
import { DAYS_OF_WEEK, orderStatusLabel } from '../../utils/labels';
import '../../styles/common/Tabs.css';
import '../../styles/farmer/FarmerOrderFilters.css';

const DAY_MS = 24 * 60 * 60 * 1000;
const dayFromToday = (days) => toApiDate(new Date(Date.now() + days * DAY_MS));

// ISO weekday (1 = Mon … 7 = Sun) of a YYYY-MM-DD date.
function isoWeekday(isoDate) {
  const day = new Date(`${isoDate}T00:00:00Z`).getUTCDay();
  return day === 0 ? 7 : day;
}

/**
 * Pickup days an open order can fall on: today through the booking horizon (D-006), keeping
 * only the farmer's operating days (D-031). Dates, not weekday names: the horizon spans 8 days,
 * so today's weekday appears twice.
 */
function openTabDays(horizonDays, operatingDays) {
  const days = [];
  for (let offset = 0; offset <= horizonDays; offset += 1) {
    const date = dayFromToday(offset);
    const weekday = isoWeekday(date);
    if (operatingDays && !operatingDays.includes(weekday)) continue;
    const name = DAYS_OF_WEEK.find((item) => item.value === weekday);
    days.push({
      id: date,
      from: date,
      to: date,
      label: offset === 0 ? 'Today' : `${name.short} ${formatDate(date).slice(0, 5)}`,
      ariaLabel: `${name.long} ${formatDate(date)}`,
    });
  }
  return days;
}

// History has no upper bound, so it filters by how far back to look.
function historyRanges() {
  const today = dayFromToday(0);
  return [
    { id: 'last7', label: 'Last 7 days', from: dayFromToday(-6), to: today },
    { id: 'last30', label: 'Last 30 days', from: dayFromToday(-29), to: today },
  ];
}

// FA-19 history statuses (backend HISTORY_STATUSES).
const HISTORY_STATUSES = ['COMPLETED', 'CANCELLED', 'DECLINED', 'NO_SHOW', 'EXPIRED'];

// FA-19 accepts `ordering` on the placed tab only (created_at | pickup_start_at). FIFO is the
// default on purpose (F-02: first ordered, first handled).
const PENDING_SORTS = [
  { value: '', label: 'Ordered first' },
  { value: 'pickup_start_at', label: 'Pickup soonest' },
];

/** Market picker shared by the order list and the picking list; hidden for a one-market stall. */
export function MarketFilter({ markets, value, onChange }) {
  if (markets.length < 2) return null;
  return (
    <div className="farmer-order-filters__field">
      <Label className="page-primitive__label-xs" htmlFor="farmer-order-market">
        Market
      </Label>
      <select
        id="farmer-order-market"
        className="page-primitive__select"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      >
        <option value={0}>All markets</option>
        {markets.map((market) => (
          <option key={market.id} value={market.id}>
            {market.name}
          </option>
        ))}
      </select>
    </div>
  );
}

MarketFilter.propTypes = {
  markets: PropTypes.arrayOf(PropTypes.shape({ id: PropTypes.number, name: PropTypes.string })).isRequired,
  value: PropTypes.number.isRequired,
  onChange: PropTypes.func.isRequired,
};

function CountBadge({ count }) {
  return count === undefined ? null : <span className="page-primitive__tab-badge">{count}</span>;
}

CountBadge.propTypes = { count: PropTypes.number };

/** Segmented control styled like the order tabs; each option can carry an order count. */
function DateSegments({ label, options, allCount, filters, setFilters }) {
  const allActive = !filters.from && !filters.to;
  return (
    <div className="farmer-order-filters__field">
      <span className="page-primitive__label-xs">{label}</span>
      <div className="tabs-list page-primitive__tabs-list-wrap" role="group" aria-label={label}>
        <button
          type="button"
          className="tabs-trigger"
          data-state={allActive ? 'active' : 'inactive'}
          aria-pressed={allActive}
          onClick={() => setFilters({ from: '', to: '' })}
        >
          All
          <CountBadge count={allCount} />
        </button>
        {options.map((option) => {
          const active = option.from === filters.from && option.to === filters.to;
          return (
            <button
              key={option.id}
              type="button"
              className={option.count === 0 ? 'tabs-trigger farmer-order-filters__segment--empty' : 'tabs-trigger'}
              data-state={active ? 'active' : 'inactive'}
              aria-pressed={active}
              aria-label={
                option.count === undefined ? option.ariaLabel : `${option.ariaLabel}, ${option.count} orders`
              }
              onClick={() => setFilters(active ? { from: '', to: '' } : { from: option.from, to: option.to })}
            >
              {option.label}
              <CountBadge count={option.count} />
            </button>
          );
        })}
      </div>
    </div>
  );
}

DateSegments.propTypes = {
  label: PropTypes.string.isRequired,
  options: PropTypes.array.isRequired,
  allCount: PropTypes.number,
  filters: PropTypes.object.isRequired,
  setFilters: PropTypes.func.isRequired,
};

// Which by_date bucket (FA-20) matches the order tab being viewed.
const COUNT_KEY_BY_TAB = { pending: 'placed', accepted: 'accepted', ready: 'ready' };

/** F-02 filter bar: search, pickup day, market, and the tab-specific status / sort. */
export function FarmerOrderFilters({
  search,
  filters,
  setFilters,
  tabId,
  markets,
  horizonDays,
  operatingDays,
  counts,
  activeCount,
  onClear,
}) {
  const isHistory = tabId === 'history';
  // Overdue orders are all in the past already; a day filter adds nothing there.
  const showDates = tabId !== 'overdue';
  const countKey = COUNT_KEY_BY_TAB[tabId];

  const dateOptions = isHistory
    ? historyRanges()
    : openTabDays(horizonDays, operatingDays).map((day) => ({
        ...day,
        count: counts && countKey ? (counts.by_date?.[day.from]?.[countKey] ?? 0) : undefined,
      }));
  const allCount = counts && countKey ? counts[countKey] : undefined;

  return (
    <div className="farmer-order-filters">
      <form
        className="farmer-order-filters__search"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          search.flush();
        }}
      >
        <Input
          type="search"
          label="Search customer or order #"
          value={search.value}
          onChange={search.onChange}
          onKeyDown={search.onKeyDown}
          className="farmer-order-filters__search-input"
        />
        {search.value ? (
          <Button type="button" size="icon" variant="ghost" aria-label="Clear search" onClick={search.clear}>
            <X aria-hidden size={16} />
          </Button>
        ) : null}
        <Button type="submit">
          <Search aria-hidden size={16} />
          Search
        </Button>
      </form>

      <div className="farmer-order-filters__row">
        {showDates ? (
          <DateSegments
            label={isHistory ? 'Picked up' : 'Pickup day'}
            options={dateOptions}
            allCount={allCount}
            filters={filters}
            setFilters={setFilters}
          />
        ) : null}

        <MarketFilter markets={markets} value={filters.market} onChange={(market) => setFilters({ market })} />

        {isHistory ? (
          <div className="farmer-order-filters__field">
            <Label className="page-primitive__label-xs" htmlFor="farmer-order-status">
              Status
            </Label>
            <select
              id="farmer-order-status"
              className="page-primitive__select"
              value={filters.status}
              onChange={(event) => setFilters({ status: event.target.value })}
            >
              <option value="">All finished</option>
              {HISTORY_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {orderStatusLabel(status)}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        {tabId === 'pending' ? (
          <div className="farmer-order-filters__field">
            <Label className="page-primitive__label-xs" htmlFor="farmer-order-sort">
              Sort by
            </Label>
            <select
              id="farmer-order-sort"
              className="page-primitive__select"
              value={filters.sort}
              onChange={(event) => setFilters({ sort: event.target.value })}
            >
              {PENDING_SORTS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        {activeCount > 0 ? (
          <Button type="button" variant="ghost" size="sm" onClick={onClear} className="farmer-order-filters__clear">
            Clear filters ({activeCount})
          </Button>
        ) : null}
      </div>
    </div>
  );
}

FarmerOrderFilters.propTypes = {
  search: PropTypes.shape({
    value: PropTypes.string.isRequired,
    onChange: PropTypes.func.isRequired,
    onKeyDown: PropTypes.func.isRequired,
    flush: PropTypes.func.isRequired,
    clear: PropTypes.func.isRequired,
  }).isRequired,
  filters: PropTypes.shape({
    from: PropTypes.string.isRequired,
    to: PropTypes.string.isRequired,
    market: PropTypes.number.isRequired,
    status: PropTypes.string.isRequired,
    sort: PropTypes.string.isRequired,
  }).isRequired,
  setFilters: PropTypes.func.isRequired,
  tabId: PropTypes.string.isRequired,
  markets: PropTypes.array.isRequired,
  horizonDays: PropTypes.number.isRequired,
  // Null until the profile loads: every day in the horizon is shown meanwhile.
  operatingDays: PropTypes.arrayOf(PropTypes.number),
  // FA-20 tab-counts (with by_date); undefined while loading, so no badges show.
  counts: PropTypes.object,
  activeCount: PropTypes.number.isRequired,
  onClear: PropTypes.func.isRequired,
};
