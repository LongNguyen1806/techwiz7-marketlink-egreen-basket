import { useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { ArrowRightLeft, CalendarCheck, CalendarClock, PackageX, Pencil, Save } from 'lucide-react';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { FarmerOrderActions } from '../../components/farmer/FarmerOrderActions';
import { isSellingMarket } from '../../components/farmer/MarketChecklist';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import { Input } from '../../components/ui/Input';
import { ROUTES } from '../../constants/routes';
import {
  useApplyWeeklyTemplate,
  useWeeklyTemplatePreview,
  useUpdateInventoryItem,
} from '../../hooks/queries/farmer/useFarmerProducts';
import { useFarmerMarkets } from '../../hooks/queries/farmer/useFarmerMarkets';
import { notify } from '../../lib/toast';
import { formatPickupWindow } from '../../utils/formatters';
import { perUnitLabel } from '../../utils/labels';
import '../../styles/farmer/FarmerStockTemplatePage.css';

const MAX_STOCK = 99999;

const isOut = (row) => row.current_stock === 0;
const hasWeekly = (row) => row.weekly_default_quantity !== null;
// new_stock is worked out by the server: weekly stock minus what accepted orders already hold.
const willChange = (row) => hasWeekly(row) && row.new_stock !== row.current_stock;

const weeklyText = (value) => (value === null || value === undefined ? '' : String(value));

function stockBadge(row) {
  if (!row.is_available) return { label: 'Paused', variant: 'secondary' };
  if (isOut(row)) return { label: 'Out of stock', variant: 'danger' };
  return null;
}

// Digits only: a number input would still accept "e", "-" or "." and hand back an empty value.
const digitsOnly = (text) => text.replace(/\D/g, '').slice(0, String(MAX_STOCK).length);

function parseQuantity(text) {
  if (text === '') return undefined;
  const value = Number(text);
  return value <= MAX_STOCK ? value : undefined;
}

function StockRow({ row, onUpdate, isUpdating, onApply, isApplying, applyLocked }) {
  const [editing, setEditing] = useState(false);
  const [stock, setStock] = useState('');
  const [weeklyDefault, setWeeklyDefault] = useState('');

  const startEdit = () => {
    setStock(String(row.current_stock));
    setWeeklyDefault(weeklyText(row.weekly_default_quantity));
    setEditing(true);
  };

  const nextStock = parseQuantity(stock);
  const nextWeekly = weeklyDefault.trim() === '' ? null : parseQuantity(weeklyDefault);
  const invalid = nextStock === undefined || nextWeekly === undefined;
  const isDirty = nextStock !== row.current_stock || nextWeekly !== row.weekly_default_quantity;

  const handleSave = () => {
    if (invalid) return;
    if (!isDirty) {
      setEditing(false);
      return;
    }
    onUpdate(
      { id: row.product_id, stock_quantity: nextStock, weekly_default_quantity: nextWeekly },
      { onSuccess: () => setEditing(false) },
    );
  };

  const onKeyDown = (event) => {
    if (event.key === 'Enter') handleSave();
    if (event.key === 'Escape') setEditing(false);
  };

  const badge = stockBadge(row);
  const canApply = willChange(row);
  const applyHint =
    row.held_quantity > 0
      ? `${row.weekly_default_quantity} weekly − ${row.held_quantity} already ordered by customers`
      : 'Same as your weekly stock';

  return (
    <tr className="page-primitive__table-row">
      <td className="page-primitive__table-td">
        <p className="page-primitive__font-medium">{row.name}</p>
        <div className="farmer-stock-template-page__meta">
          <span className="page-primitive__muted-xs">{perUnitLabel(row.unit)}</span>
          {badge ? <Badge variant={badge.variant}>{badge.label}</Badge> : null}
        </div>
      </td>

      <td className="page-primitive__table-td">
        {editing ? (
          <Input
            type="text"
            inputMode="numeric"
            autoComplete="off"
            autoFocus
            aria-label={`Stock for ${row.name}`}
            aria-invalid={nextStock === undefined}
            className="farmer-stock-template-page__qty-input"
            value={stock}
            disabled={isUpdating}
            onChange={(event) => setStock(digitsOnly(event.target.value))}
            onKeyDown={onKeyDown}
          />
        ) : (
          <>
            <p className="page-primitive__font-medium">{row.current_stock}</p>
            {canApply ? (
              <p className="page-primitive__muted-xs" title={applyHint}>
                After apply: {row.new_stock}
              </p>
            ) : null}
          </>
        )}
      </td>

      <td className="page-primitive__table-td">
        {editing ? (
          <Input
            type="text"
            inputMode="numeric"
            autoComplete="off"
            aria-label={`Weekly stock for ${row.name} (leave empty for none)`}
            aria-invalid={nextWeekly === undefined}
            className="farmer-stock-template-page__qty-input"
            value={weeklyDefault}
            disabled={isUpdating}
            onChange={(event) => setWeeklyDefault(digitsOnly(event.target.value))}
            onKeyDown={onKeyDown}
          />
        ) : row.weekly_default_quantity === null ? (
          <span className="page-primitive__muted-xs">Not set</span>
        ) : (
          <span>{row.weekly_default_quantity}</span>
        )}
      </td>

      <td className="page-primitive__table-td">
        {editing ? (
          <div className="farmer-stock-template-page__row-actions">
            <Button size="sm" onClick={handleSave} loading={isUpdating} disabled={invalid}>
              <Save aria-hidden className="farmer-stock-template-page__btn-icon" /> Save
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)} disabled={isUpdating}>
              Cancel
            </Button>
          </div>
        ) : (
          <div className="farmer-stock-template-page__row-actions">
            <Button size="sm" variant="outline" onClick={startEdit} disabled={isApplying}>
              <Pencil aria-hidden className="farmer-stock-template-page__btn-icon" /> Edit
            </Button>
            <Button
              data-write
              size="sm"
              variant="outline"
              title={hasWeekly(row) ? `Set current stock to ${row.new_stock}` : 'Set a weekly stock first'}
              onClick={() => onApply(row)}
              loading={isApplying}
              disabled={!hasWeekly(row) || applyLocked}
            >
              <CalendarCheck aria-hidden className="farmer-stock-template-page__btn-icon" /> Apply
            </Button>
          </div>
        )}
      </td>
    </tr>
  );
}

StockRow.propTypes = {
  row: PropTypes.object.isRequired,
  onUpdate: PropTypes.func.isRequired,
  isUpdating: PropTypes.bool.isRequired,
  onApply: PropTypes.func.isRequired,
  isApplying: PropTypes.bool.isRequired,
  applyLocked: PropTypes.bool.isRequired,
};

export default function FarmerStockTemplatePage() {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [market, setMarket] = useState(0);
  const [category, setCategory] = useState(0);
  const [updatingId, setUpdatingId] = useState(null);

  const previewQuery = useWeeklyTemplatePreview();
  const marketsQuery = useFarmerMarkets();
  const apply = useApplyWeeklyTemplate();
  const updateItem = useUpdateInventoryItem();

  const handleUpdate = (payload, { onSuccess }) => {
    setUpdatingId(payload.id);
    updateItem.mutate(payload, { onSuccess, onSettled: () => setUpdatingId(null) });
  };

  const applyRow = (row) => {
    if (!willChange(row)) {
      notify.info(`${row.name} is already at its weekly stock`);
      return;
    }
    apply.mutate([row.product_id]);
  };
  const applyingId = apply.isPending && apply.variables?.length === 1 ? apply.variables[0] : null;

  const data = previewQuery.data;
  const rows = useMemo(() => data?.rows ?? [], [data]);
  const overdueOrders = data?.overdue_orders ?? [];
  const markets = (marketsQuery.data ?? []).filter(isSellingMarket);

  const categories = useMemo(() => {
    const byId = new Map(rows.map((row) => [row.category.id, row.category]));
    return [...byId.values()].sort((a, b) => a.name.localeCompare(b.name));
  }, [rows]);

  const shownRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return rows.filter(
      (row) =>
        (!market || row.market_ids.includes(market)) &&
        (!category || row.category.id === category) &&
        (!query || row.name.toLowerCase().includes(query)),
    );
  }, [rows, market, category, search]);

  const isFiltered = shownRows.length !== rows.length;
  const withWeekly = shownRows.filter(hasWeekly);
  const changing = shownRows.filter(willChange);
  const changingEverywhere = rows.filter(willChange);
  // Send ids only when the filter hides some changing rows; otherwise apply to everything.
  const applyIds = changing.length === changingEverywhere.length ? undefined : changing.map((row) => row.product_id);

  const confirmApply = () => {
    if (changing.length === 0) {
      setConfirmOpen(false);
      return;
    }
    apply.mutate(applyIds, { onSuccess: () => setConfirmOpen(false) });
  };

  if (previewQuery.isPending) return <PageSkeleton />;
  if (!data) {
    return (
      <EmptyState title="Stock data couldn't be loaded" actionLabel="Try again" onAction={() => previewQuery.refetch()} />
    );
  }

  const kpis = [
    { label: 'Products with weekly stock', value: `${rows.filter(hasWeekly).length} of ${rows.length}`, icon: CalendarClock },
    { label: 'Need filling up', value: changingEverywhere.length, icon: ArrowRightLeft },
    { label: 'Sold out', value: rows.filter(isOut).length, icon: PackageX },
  ];

  return (
    <div className="farmer-stock-template-page">
      <PageHeader
        title="Weekly stock"
        description="Write down how much of each product you usually have every week. Press Apply to fill your stock back up to that amount. Change the numbers any time your harvest changes."
      />

      <div className="farmer-stock-template-page__kpis">
        {kpis.map((item) => (
          <Card key={item.label}>
            <CardHeader className="page-primitive__card-header-row page-primitive__card-header-tight">
              <CardTitle className="page-primitive__card-title-muted">{item.label}</CardTitle>
              <item.icon aria-hidden className="page-primitive__kpi-icon" />
            </CardHeader>
            <CardContent>
              <p className="page-primitive__stat-value">{item.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="farmer-stock-template-page__apply-bar">
        <div>
          <p className="page-primitive__semibold">Fill stock up to the weekly amount</p>
          <p className="page-primitive__muted-sm">
            Each product goes back to its weekly stock, minus what customers have already ordered.{' '}
            {changing.length === 0
              ? 'Everything is already full.'
              : `${changing.length} product${changing.length === 1 ? '' : 's'}${isFiltered ? ' shown' : ''} will be filled up.`}
          </p>
        </div>
        <Button data-write disabled={withWeekly.length === 0 || apply.isPending} onClick={() => setConfirmOpen(true)}>
          <CalendarCheck aria-hidden className="farmer-stock-template-page__btn-icon" />
          {isFiltered ? `Apply to ${withWeekly.length} shown` : 'Apply to all'}
        </Button>
      </div>

      {overdueOrders.length > 0 ? (
        <div className="page-primitive__warn-panel">
          <p className="page-primitive__semibold">
            {overdueOrders.length} order{overdueOrders.length === 1 ? ' is' : 's are'} past pickup and still open
          </p>
          <p className="page-primitive__muted-sm">
            Close them first so the weekly stock is worked out from what was actually picked up.
          </p>
          <ul className="page-primitive__warn-list page-primitive__list-plain">
            {overdueOrders.map((order) => (
              <li key={order.id} className="page-primitive__list-item-row">
                <Link className="page-primitive__link-underline" to={ROUTES.FARMER.ORDER(order.id)}>
                  #{order.id} · {order.customer.full_name} ·{' '}
                  {formatPickupWindow(order.pickup_start_at, order.pickup_end_at)}
                </Link>
                <FarmerOrderActions order={order} />
              </li>
            ))}
          </ul>
          <Button asChild size="sm" className="page-primitive__mt-3" variant="outline">
            <Link to={`${ROUTES.FARMER.ORDERS}?tab=overdue`}>Handle overdue orders</Link>
          </Button>
        </div>
      ) : null}

      {markets.length > 1 ? (
        <div className="farmer-stock-template-page__chips" role="group" aria-label="Filter by market">
          <button
            type="button"
            className={`farmer-stock-template-page__chip${!market ? ' is-active' : ''}`}
            onClick={() => setMarket(0)}
          >
            All markets
          </button>
          {markets.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`farmer-stock-template-page__chip${market === item.market.id ? ' is-active' : ''}`}
              onClick={() => setMarket(item.market.id)}
            >
              {item.market.name}
            </button>
          ))}
        </div>
      ) : null}

      <form className="page-primitive__actions-row" role="search" onSubmit={(event) => event.preventDefault()}>
        <Input
          type="search"
          label="Search produce"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="page-primitive__input-narrow"
        />
        <select
          className="page-primitive__select"
          aria-label="Filter by category"
          value={category}
          onChange={(event) => setCategory(Number(event.target.value))}
        >
          <option value={0}>All categories</option>
          {categories.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </form>

      {shownRows.length === 0 ? (
        <EmptyState
          title="No produce found"
          description={
            rows.length === 0 ? 'Add produce first, then set its weekly stock here.' : 'No products match these filters.'
          }
        />
      ) : (
        <div className="page-primitive__table-wrap" aria-busy={previewQuery.isFetching}>
          <table className="page-primitive__table">
            <thead className="page-primitive__table-head">
              <tr>
                <th className="page-primitive__table-th">Product</th>
                <th className="page-primitive__table-th" title="What shoppers can order right now">
                  Current Stock
                </th>
                <th className="page-primitive__table-th" title="Used when you apply the weekly stock">
                  Weekly stock
                </th>
                <th className="page-primitive__table-th">Action</th>
              </tr>
            </thead>
            <tbody>
              {shownRows.map((row) => (
                <StockRow
                  key={row.product_id}
                  row={row}
                  onUpdate={handleUpdate}
                  isUpdating={updatingId === row.product_id}
                  onApply={applyRow}
                  isApplying={applyingId === row.product_id}
                  applyLocked={apply.isPending}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={changing.length === 0 ? 'Everything is already full' : 'Fill stock up to the weekly amount?'}
        description={
          changing.length === 0
            ? 'Every product is already at its weekly stock, so nothing will change.'
            : `${changing.length} product${changing.length === 1 ? '' : 's'} will go back to the weekly stock, minus what customers have already ordered.`
        }
        confirmLabel={changing.length === 0 ? 'OK' : 'Apply'}
        loading={apply.isPending}
        onConfirm={confirmApply}
      />
    </div>
  );
}
