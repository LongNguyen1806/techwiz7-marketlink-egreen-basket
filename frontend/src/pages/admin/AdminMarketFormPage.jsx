import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate, useParams } from 'react-router-dom';
import { MapContainer, Marker, TileLayer, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import 'leaflet/dist/leaflet.css';

import {
  useAdminMarket,
  useSaveAdminMarket,
} from '../../hooks/queries/admin/useAdminMarkets';
import { marketSchema } from '../../schemas/admin/market.schema';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Label } from '../../components/ui/Label';
import { Textarea } from '../../components/ui/Textarea';
import { MarketClosuresPanel } from '../../components/admin/MarketClosuresPanel';
import { ApiError } from '../../lib/ApiError';
import { mapServerErrorsToForm } from '../../utils/mapServerErrors';

import '../../styles/admin/AdminMarketFormPage.css';

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const DAYS = [
  { value: 1, label: 'Mon' },
  { value: 2, label: 'Tue' },
  { value: 3, label: 'Wed' },
  { value: 4, label: 'Thu' },
  { value: 5, label: 'Fri' },
  { value: 6, label: 'Sat' },
  { value: 7, label: 'Sun' },
];

const DEFAULT_VALUES = {
  name: '',
  address: '',
  latitude: 10.7725,
  longitude: 106.698,
  image:
    'https://images.unsplash.com/photo-1488459716781-31db52582fe9?auto=format&fit=crop&w=800&q=80',
  open_time: '06:00',
  close_time: '18:00',
  operating_days: [1, 3, 5],
  description: '',
};

function MapClick({ onPick }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function readDragLatLng(target) {
  if (!target || typeof target !== 'object' || !('getLatLng' in target)) return null;
  const getter = target.getLatLng;
  if (typeof getter !== 'function') return null;
  const point = getter.call(target);
  if (!point || typeof point !== 'object') return null;
  if (!('lat' in point) || !('lng' in point)) return null;
  if (typeof point.lat !== 'number' || typeof point.lng !== 'number') return null;
  return { lat: point.lat, lng: point.lng };
}

export default function AdminMarketFormPage() {
  const { id } = useParams();
  const marketId = id ? Number(id) : NaN;
  const isEdit = Number.isFinite(marketId);
  const navigate = useNavigate();
  const [seededId, setSeededId] = useState(null);

  const marketQuery = useAdminMarket(marketId, isEdit);
  const save = useSaveAdminMarket(isEdit ? marketId : undefined);
  const form = useForm({
    resolver: zodResolver(marketSchema),
    defaultValues: DEFAULT_VALUES,
  });

  const market = marketQuery.data;

  useEffect(() => {
    if (!isEdit || !market || seededId === market.id) return;
    form.reset({
      name: market.name,
      address: market.address,
      latitude: market.latitude,
      longitude: market.longitude,
      image: market.image ?? '',
      open_time: market.open_time,
      close_time: market.close_time,
      operating_days: market.operating_days,
      description: market.description ?? '',
    });
    setSeededId(market.id);
  }, [form, isEdit, market, seededId]);

  const latitude = form.watch('latitude');
  const longitude = form.watch('longitude');
  const operatingDays = form.watch('operating_days') || [];

  if (isEdit && marketQuery.isLoading) return <PageSkeleton />;
  if (isEdit && (marketQuery.isError || !marketQuery.data)) {
    return (
      <EmptyState
        title="Market couldn't be loaded"
        actionLabel="Try again"
        onAction={() => marketQuery.refetch()}
      />
    );
  }
  if (isEdit && seededId !== market?.id) return <PageSkeleton />;

  const toggleDay = (day) => {
    const current = form.getValues('operating_days') || [];
    const next = current.includes(day)
      ? current.filter((value) => value !== day)
      : [...current, day];
    form.setValue('operating_days', next, { shouldValidate: true });
  };

  const onSubmit = (values) => {
    save.mutate(
      {
        name: values.name,
        address: values.address,
        latitude: values.latitude,
        longitude: values.longitude,
        image: values.image || null,
        open_time: values.open_time,
        close_time: values.close_time,
        operating_days: values.operating_days,
        description: values.description || null,
      },
      {
        onSuccess: () => navigate('/admin/markets'),
        onError: (error) => {
          mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, form.setError);
        },
      },
    );
  };

  return (
    <form className="admin-market-form-page" onSubmit={form.handleSubmit(onSubmit)}>
      <PageHeader title={isEdit ? 'Edit market' : 'Add a market'} />
      <div className="admin-market-form-page__body">
        <div className="admin-market-form-page__fields">
          <div className="page-primitive__form-grid-2">
            <div className="page-primitive__form-field page-primitive__form-span-2">
              <Input
                id="name"
                label="Market name"
                requiredMark
                {...form.register('name')}
              />
              {form.formState.errors.name ? (
                <p className="page-primitive__error">{form.formState.errors.name.message}</p>
              ) : null}
            </div>
            <div className="page-primitive__form-field page-primitive__form-span-2">
              <Input
                id="address"
                label="Address"
                requiredMark
                {...form.register('address')}
              />
              {form.formState.errors.address ? (
                <p className="page-primitive__error">
                  {form.formState.errors.address.message}
                </p>
              ) : null}
            </div>
            <div className="page-primitive__form-field">
              <Input
                id="open_time"
                type="time"
                label="Open time"
                requiredMark
                {...form.register('open_time')}
              />
              {form.formState.errors.open_time ? (
                <p className="page-primitive__error">
                  {form.formState.errors.open_time.message}
                </p>
              ) : null}
            </div>
            <div className="page-primitive__form-field">
              <Input
                id="close_time"
                type="time"
                label="Close time"
                requiredMark
                {...form.register('close_time')}
              />
              {form.formState.errors.close_time ? (
                <p className="page-primitive__error">
                  {form.formState.errors.close_time.message}
                </p>
              ) : null}
            </div>
          </div>

          <div>
            <Label>Market days</Label>
            <div className="admin-market-form-page__days">
              {DAYS.map((day) => (
                <button
                  key={day.value}
                  type="button"
                  onClick={() => toggleDay(day.value)}
                  className={
                    operatingDays.includes(day.value)
                      ? 'admin-market-form-page__day admin-market-form-page__day--active'
                      : 'admin-market-form-page__day'
                  }
                >
                  {day.label}
                </button>
              ))}
            </div>
            {form.formState.errors.operating_days ? (
              <p className="page-primitive__error page-primitive__mt-2">
                {form.formState.errors.operating_days.message}
              </p>
            ) : null}
          </div>

          <div className="page-primitive__form-field">
            <Label htmlFor="description">Description</Label>
            <Textarea id="description" {...form.register('description')} />
          </div>

          {isEdit ? <MarketClosuresPanel marketId={marketId} /> : null}
        </div>

        <div className="admin-market-form-page__map">
          <div className="page-primitive__map-box">
            <MapContainer
              center={[latitude, longitude]}
              zoom={15}
              className="page-primitive__map-fill"
            >
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <Marker
                position={[latitude, longitude]}
                draggable
                eventHandlers={{
                  dragend: (event) => {
                    const point = readDragLatLng(event.target);
                    if (!point) return;
                    form.setValue('latitude', point.lat);
                    form.setValue('longitude', point.lng);
                  },
                }}
              />
              <MapClick
                onPick={(nextLatitude, nextLongitude) => {
                  form.setValue('latitude', nextLatitude);
                  form.setValue('longitude', nextLongitude);
                }}
              />
            </MapContainer>
          </div>
        </div>
      </div>

      <div className="admin-market-form-page__actions">
        <Button
          type="button"
          variant="outline"
          onClick={() => navigate('/admin/markets')}
        >
          Cancel
        </Button>
        <Button type="submit" loading={save.isPending}>
          Save
        </Button>
      </div>
    </form>
  );
}
