import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'react-router-dom';
import { MapContainer, Marker, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { MARKER_ICON } from '../../components/common/maps/markerIcon';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Switch } from '../../components/ui/Switch';
import { ROUTES } from '../../constants/routes';
import {
  useCreatePickupSlot,
  useFarmerMarkets,
  useJoinMarket,
  useLeaveMarket,
  useTogglePickupSlot,
  useUpdateStallLabel,
} from '../../hooks/queries/farmer/useFarmerMarkets';
import { useFarmerProfile } from '../../hooks/queries/farmer/useFarmerProfile';
import { usePublicMarkets } from '../../hooks/queries/guest/usePublicCatalog';
import { ApiError } from '../../lib/ApiError';
import { joinMarketSchema, makePickupSlotSchema, stallLabelSchema } from '../../schemas/farmer/market.schema';
import { formatTimeRange } from '../../utils/formatters';
import { DAYS_OF_WEEK, dayOfWeekLabel } from '../../utils/labels';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';
import '../../styles/farmer/FarmerMarketsPage.css';





const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

const PUBLIC_MARKETS_PARAMS = { page_size: 20 };
const DEFAULT_SLOT_MINUTES = 120;

function addMinutes(hhmm, minutes) {
  const [h, m] = hhmm.split(':').map(Number);
  const total = Math.min(h * 60 + m + minutes, 23 * 60 + 59);
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
}

function FieldError({ error }) {
  return error ? <p className="page-primitive__error">{error.message}</p> : null;
}

FieldError.propTypes = { error: PropTypes.shape({ message: PropTypes.string }) };

function JoinMarketPanel({ joinedMarketIds, onJoined }) {
  const publicMarkets = usePublicMarkets(PUBLIC_MARKETS_PARAMS);
  const join = useJoinMarket();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm({ resolver: zodResolver(joinMarketSchema), defaultValues: { market_id: 0, stall_label: '' } });

  const available = (publicMarkets.data?.results ?? []).filter((market) => !joinedMarketIds.has(market.id));

  const onSubmit = handleSubmit((values) =>
    join.mutate(
      { marketId: values.market_id, stallLabel: values.stall_label },
      {
        onSuccess: (item) => {
          reset();
          onJoined(item.id);
        },
        onError: (error) =>
          mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError, {
            fields: ['market_id', 'stall_label'],
          }),
      },
    ),
  );

  return (
    <form className="page-primitive__dashed-panel" onSubmit={onSubmit} noValidate>
      <p className="page-primitive__font-medium">Add market</p>
      <select
        className="page-primitive__select-full"
        aria-label="Market"
        {...register('market_id', { valueAsNumber: true })}
      >
        <option value={0}>{publicMarkets.isPending ? 'Loading markets…' : 'Select market…'}</option>
        {available.map((market) => (
          <option key={market.id} value={market.id}>
            {market.name}
          </option>
        ))}
      </select>
      <FieldError error={errors.market_id} />
      <Input label="Stall label (e.g. Aisle A · Stall 12)" maxLength={100} {...register('stall_label')} />
      <FieldError error={errors.stall_label} />
      <FieldError error={errors.root?.server} />
      <Button type="submit" className="page-primitive__btn-full" loading={join.isPending}>
        Add market
      </Button>
    </form>
  );
}

JoinMarketPanel.propTypes = {
  joinedMarketIds: PropTypes.instanceOf(Set).isRequired,
  onJoined: PropTypes.func.isRequired,
};

function StallLabelForm({ farmerMarket }) {
  const update = useUpdateStallLabel();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isDirty },
  } = useForm({
    resolver: zodResolver(stallLabelSchema),
    values: { stall_label: farmerMarket.stall_label },
  });

  const onSubmit = handleSubmit((values) =>
    update.mutate(
      { farmerMarketId: farmerMarket.id, stallLabel: values.stall_label },
      {
        onError: (error) =>
          mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError, { fields: ['stall_label'] }),
      },
    ),
  );

  return (
    <form className="page-primitive__form-field" onSubmit={onSubmit} noValidate>
      <div className="page-primitive__inline-row">
        <Input label="Stall label" maxLength={100} {...register('stall_label')} />
        <Button type="submit" loading={update.isPending} disabled={!isDirty}>
          Save
        </Button>
      </div>
      <FieldError error={errors.stall_label} />
    </form>
  );
}

StallLabelForm.propTypes = { farmerMarket: PropTypes.object.isRequired };

function AddSlotDialog({ farmerMarket, day, onClose }) {
  const create = useCreatePickupSlot();
  const { open_time: openTime, close_time: closeTime } = farmerMarket.market;
  const schema = useMemo(
    () => makePickupSlotSchema({ openTime, closeTime, existingSlots: farmerMarket.slots }),
    [openTime, closeTime, farmerMarket.slots],
  );
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (day === null) return;
    const start = openTime ?? '07:00';
    const end = addMinutes(start, DEFAULT_SLOT_MINUTES);
    reset({ day_of_week: day, start_time: start, end_time: closeTime && end > closeTime ? closeTime : end });
  }, [day, openTime, closeTime, reset]);

  const onSubmit = handleSubmit((values) =>
    create.mutate(
      {
        farmerMarketId: farmerMarket.id,
        dayOfWeek: values.day_of_week,
        startTime: values.start_time,
        endTime: values.end_time,
      },
      {
        onSuccess: onClose,
        onError: (error) =>
          mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, setError, {
            fields: ['day_of_week', 'start_time', 'end_time'],
          }),
      },
    ),
  );

  return (
    <ConfirmDialog
      open={day !== null}
      onOpenChange={(open) => !open && onClose()}
      title={`Add a ${dayOfWeekLabel(day) || ''} pickup slot`}
      description={openTime && closeTime ? `This market is open ${formatTimeRange(openTime, closeTime)}.` : undefined}
      confirmLabel="Add slot"
      loading={create.isPending}
      onConfirm={() => void onSubmit()}
    >
      <div className="page-primitive__form-grid-2">
        <div className="page-primitive__form-field">
          <Input type="time" label="Starts" {...register('start_time')} />
          <FieldError error={errors.start_time} />
        </div>
        <div className="page-primitive__form-field">
          <Input type="time" label="Ends" {...register('end_time')} />
          <FieldError error={errors.end_time} />
        </div>
      </div>
      <FieldError error={errors.day_of_week} />
      <FieldError error={errors.root?.server} />
    </ConfirmDialog>
  );
}

AddSlotDialog.propTypes = {
  farmerMarket: PropTypes.object.isRequired,
  day: PropTypes.number,
  onClose: PropTypes.func.isRequired,
};

function MarketDetail({ farmerMarket, farmerDays, onLeft }) {
  const toggleSlot = useTogglePickupSlot();
  const leave = useLeaveMarket();
  const [slotDay, setSlotDay] = useState(null);
  const [confirmLeave, setConfirmLeave] = useState(false);
  const { market } = farmerMarket;
  const hasCoordinates = typeof market.latitude === 'number' && typeof market.longitude === 'number';

  
  const dayState = (day) => {
    if (!market.operating_days.includes(day)) return { enabled: false, reason: 'The market is closed on this day' };
    if (farmerDays && !farmerDays.includes(day)) return { enabled: false, reason: 'Not one of your operating days' };
    return { enabled: true, reason: undefined };
  };
  
  const bookableDays = DAYS_OF_WEEK.filter((day) => dayState(day.value).enabled).map((day) => day.short);

  return (
    <>
      {!farmerMarket.is_market_active ? (
        <p className="page-primitive__warn-banner">
          An administrator has closed this market. Its pickup slots are off and new orders can&apos;t be placed here.
        </p>
      ) : null}

      <StallLabelForm key={farmerMarket.id} farmerMarket={farmerMarket} />

      {hasCoordinates ? (
        <div className="page-primitive__map-h-64">
          
          <MapContainer
            key={farmerMarket.id}
            center={[market.latitude, market.longitude]}
            zoom={16}
            className="page-primitive__map-fill"
          >
            <TileLayer attribution={OSM_ATTRIBUTION} url={OSM_TILE_URL} />
            <Marker position={[market.latitude, market.longitude]} icon={MARKER_ICON} />
          </MapContainer>
        </div>
      ) : null}

      <div>
        <div className="farmer-markets-page__slots-head">
          <h3 className="page-primitive__heading">Weekly pickup slots</h3>
        </div>
        <div className="page-primitive__actions-row farmer-markets-page__slots-actions">
          {DAYS_OF_WEEK.map((day) => {
            const { enabled, reason } = dayState(day.value);
            return (
              <Button
                key={day.value}
                size="sm"
                variant="outline"
                disabled={!enabled || !farmerMarket.is_market_active}
                title={reason}
                aria-label={`Add a ${day.long} slot`}
                onClick={() => setSlotDay(day.value)}
              >
                + {day.short}
              </Button>
            );
          })}
        </div>
        {farmerMarket.is_market_active ? (
          <p className="page-primitive__muted-xs">
            {bookableDays.length > 0
              ? `You can add slots on ${bookableDays.join(', ')}: the days this market opens and you work. `
              : "This market doesn't open on any of your working days. "}
            Change your working days in{' '}
            <Link to={ROUTES.FARMER.PROFILE} className="page-primitive__link-underline">
              Stall profile
            </Link>
            .
          </p>
        ) : null}
        <div className="page-primitive__stack-2">
          {farmerMarket.slots.length === 0 ? (
            <p className="page-primitive__muted-sm">No pickup slots yet.</p>
          ) : (
            farmerMarket.slots.map((slot) => (
              <div key={slot.id} className="page-primitive__list-item-row">
                <span>
                  {dayOfWeekLabel(slot.day_of_week, { short: true })} · {formatTimeRange(slot.start_time, slot.end_time)}
                </span>
                <Switch
                  checked={slot.is_active}
                  aria-label={`${dayOfWeekLabel(slot.day_of_week)} ${formatTimeRange(slot.start_time, slot.end_time)} open for booking`}
                  onCheckedChange={(checked) =>
                    toggleSlot.mutate({ farmerMarketId: farmerMarket.id, slotId: slot.id, isActive: checked })
                  }
                />
              </div>
            ))
          )}
        </div>
      </div>

      {farmerMarket.open_order_count > 0 ? (
        <p className="page-primitive__muted-sm">
          {farmerMarket.open_order_count} open order{farmerMarket.open_order_count === 1 ? '' : 's'} at this market.
          Complete or decline {farmerMarket.open_order_count === 1 ? 'it' : 'them'} before leaving.
        </p>
      ) : null}
      <Button
        variant="destructive"
        disabled={farmerMarket.open_order_count > 0}
        onClick={() => setConfirmLeave(true)}
      >
        Leave market
      </Button>

      <AddSlotDialog farmerMarket={farmerMarket} day={slotDay} onClose={() => setSlotDay(null)} />

      <ConfirmDialog
        open={confirmLeave}
        onOpenChange={setConfirmLeave}
        title={`Leave ${market.name}?`}
        description="Your stall and all its pickup slots at this market will be removed. Past orders keep their details."
        confirmLabel="Leave market"
        destructive
        loading={leave.isPending}
        onConfirm={() =>
          leave.mutate(
            { farmerMarketId: farmerMarket.id, marketName: market.name },
            {
              onSuccess: onLeft,
              onSettled: () => setConfirmLeave(false),
            },
          )
        }
      />
    </>
  );
}

MarketDetail.propTypes = {
  farmerMarket: PropTypes.object.isRequired,
  farmerDays: PropTypes.arrayOf(PropTypes.number),
  onLeft: PropTypes.func.isRequired,
};

export default function FarmerMarketsPage() {
  const marketsQuery = useFarmerMarkets();
  const profileQuery = useFarmerProfile();
  const [selectedId, setSelectedId] = useState(null);

  const markets = useMemo(() => marketsQuery.data ?? [], [marketsQuery.data]);
  const joinedMarketIds = useMemo(() => new Set(markets.map((item) => item.market.id)), [markets]);
  
  const selected = markets.find((item) => item.id === selectedId) ?? markets[0] ?? null;

  if (marketsQuery.isPending) return <PageSkeleton />;
  if (!marketsQuery.data) {
    return <EmptyState title="Your markets couldn't be loaded" actionLabel="Try again" onAction={() => marketsQuery.refetch()} />;
  }

  return (
    <div className="farmer-markets-page">
      <PageHeader
        title="Markets & pickup times"
        description="Join markets, set your stall label, and publish bookable pickup slots."
      />

      <div className="page-primitive__layout-5">
        <div className="page-primitive__layout-5-side">
          {markets.length === 0 ? (
            <EmptyState
              title="You have not joined a market yet"
              description="Join a market session to start receiving pre-orders."
            />
          ) : (
            markets.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-pressed={selected?.id === item.id}
                onClick={() => setSelectedId(item.id)}
                className={
                  selected?.id === item.id
                    ? 'farmer-markets-page__market-btn farmer-markets-page__market-btn--selected'
                    : 'farmer-markets-page__market-btn'
                }
              >
                <p className="page-primitive__semibold">{item.market.name}</p>
                <p className="page-primitive__muted-sm">
                  {item.stall_label}
                  {!item.is_market_active ? ' · Closed by admin' : ''}
                </p>
              </button>
            ))
          )}

          <JoinMarketPanel joinedMarketIds={joinedMarketIds} onJoined={setSelectedId} />
        </div>

        <div className="page-primitive__layout-5-main">
          {selected ? (
            <MarketDetail
              farmerMarket={selected}
              farmerDays={profileQuery.data?.operating_days}
              onLeft={() => setSelectedId(null)}
            />
          ) : (
            <EmptyState title="Select a market to set up pickup times" />
          )}
        </div>
      </div>
    </div>
  );
}
