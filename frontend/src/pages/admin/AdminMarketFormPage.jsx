import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate, useParams } from "react-router-dom";

import { useAdminMarket, useSaveAdminMarket } from "../../hooks/queries/admin/useAdminMarkets";
import { marketSchema } from "../../schemas/admin/market.schema";
import { EmptyState } from "../../components/feedback/EmptyState";
import { PageHeader } from "../../components/common/PageHeader";
import { PageSkeleton } from "../../components/feedback/PageSkeleton";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Label } from "../../components/ui/Label";
import { Textarea } from "../../components/ui/Textarea";
import { MarketClosuresPanel } from "../../components/admin/MarketClosuresPanel";
import { MapPicker } from "../../components/common/maps/MapPicker";
import { ApiError } from "../../lib/ApiError";
import { mapServerErrorsToForm } from "../../utils/mapServerErrors";

import "../../styles/admin/AdminMarketFormPage.css";

const DAYS = [
  { value: 1, label: "Mon" },
  { value: 2, label: "Tue" },
  { value: 3, label: "Wed" },
  { value: 4, label: "Thu" },
  { value: 5, label: "Fri" },
  { value: 6, label: "Sat" },
  { value: 7, label: "Sun" },
];

const DEFAULT_VALUES = {
  name: "",
  address: "",
  // No pin until the admin places one: a default spot would send shoppers to the wrong place
  // whenever it was left unmoved.
  latitude: null,
  longitude: null,
  image: "https://images.unsplash.com/photo-1488459716781-31db52582fe9?auto=format&fit=crop&w=800&q=80",
  open_time: "06:00",
  close_time: "18:00",
  operating_days: [1, 3, 5],
  description: "",
};

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
      image: market.image ?? "",
      open_time: market.open_time,
      close_time: market.close_time,
      operating_days: market.operating_days,
      description: market.description ?? "",
    });
    setSeededId(market.id);
  }, [form, isEdit, market, seededId]);

  const [address, latitude, longitude] = form.watch(["address", "latitude", "longitude"]);
  const pinError = form.formState.errors.latitude ?? form.formState.errors.longitude;
  const operatingDays = form.watch("operating_days") || [];

  if (isEdit && marketQuery.isLoading) return <PageSkeleton />;
  if (isEdit && (marketQuery.isError || !marketQuery.data)) {
    return <EmptyState title="Market couldn't be loaded" actionLabel='Try again' onAction={() => marketQuery.refetch()} />;
  }
  if (isEdit && seededId !== market?.id) return <PageSkeleton />;

  const toggleDay = (day) => {
    const current = form.getValues("operating_days") || [];
    const next = current.includes(day) ? current.filter((value) => value !== day) : [...current, day];
    form.setValue("operating_days", next, { shouldValidate: true });
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
        onSuccess: () => navigate("/admin/markets"),
        onError: (error) => {
          mapServerErrorsToForm(ApiError.fromUnknown(error).fieldErrors, form.setError);
        },
      },
    );
  };

  return (
    <form className='admin-market-form-page' onSubmit={form.handleSubmit(onSubmit)}>
      <PageHeader title={isEdit ? "Edit market" : "Add a market"} />
      <div className='admin-market-form-page__body'>
        <div className='admin-market-form-page__fields'>
          <div className='page-primitive__form-grid-2'>
            <div className='page-primitive__form-field page-primitive__form-span-2'>
              <Input id='name' label='Market name' requiredMark {...form.register("name")} />
              {form.formState.errors.name ? <p className='page-primitive__error'>{form.formState.errors.name.message}</p> : null}
            </div>
            <div className='page-primitive__form-field page-primitive__form-span-2'>
              <Input id='address' label='Address' requiredMark {...form.register("address")} />
              {form.formState.errors.address ? <p className='page-primitive__error'>{form.formState.errors.address.message}</p> : null}
            </div>
            <div className='page-primitive__form-field'>
              <Input id='open_time' type='time' label='Open time' requiredMark {...form.register("open_time")} />
              {form.formState.errors.open_time ? <p className='page-primitive__error'>{form.formState.errors.open_time.message}</p> : null}
            </div>
            <div className='page-primitive__form-field'>
              <Input id='close_time' type='time' label='Close time' requiredMark {...form.register("close_time")} />
              {form.formState.errors.close_time ? <p className='page-primitive__error'>{form.formState.errors.close_time.message}</p> : null}
            </div>
          </div>

          <div>
            <Label>Market days</Label>
            <div className='admin-market-form-page__days'>
              {DAYS.map((day) => (
                <button
                  key={day.value}
                  type='button'
                  onClick={() => toggleDay(day.value)}
                  className={operatingDays.includes(day.value) ? "admin-market-form-page__day admin-market-form-page__day--active" : "admin-market-form-page__day"}>
                  {day.label}
                </button>
              ))}
            </div>
            {form.formState.errors.operating_days ? <p className='page-primitive__error page-primitive__mt-2'>{form.formState.errors.operating_days.message}</p> : null}
          </div>

          <div className='page-primitive__form-field'>
            <Label htmlFor='description'>Description</Label>
            <Textarea id='description' {...form.register("description")} />
          </div>

          {isEdit ? <MarketClosuresPanel marketId={marketId} /> : null}
        </div>

        <div className='admin-market-form-page__map'>
          <Label>Location on the map</Label>
          <p className='page-primitive__muted-sm'>
            Shoppers get directions to this pin. Find the address, then drag the pin onto the market entrance.
          </p>
          <MapPicker
            address={address}
            latitude={latitude}
            longitude={longitude}
            onChange={(point) => {
              form.setValue("latitude", point.latitude, { shouldDirty: true, shouldValidate: form.formState.isSubmitted });
              form.setValue("longitude", point.longitude, { shouldDirty: true, shouldValidate: form.formState.isSubmitted });
            }}
          />
          {pinError ? <p className='page-primitive__error'>{pinError.message}</p> : null}
        </div>
      </div>

      <div className='admin-market-form-page__actions'>
        <Button type='button' variant='outline' onClick={() => navigate("/admin/markets")}>
          Cancel
        </Button>
        <Button type='submit' loading={save.isPending}>
          Save
        </Button>
      </div>
    </form>
  );
}
