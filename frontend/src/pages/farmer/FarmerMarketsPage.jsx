import { useMemo, useState } from 'react';
import { MapContainer, Marker, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import 'leaflet/dist/leaflet.css';
import { useAddFarmerMarket, useCreatePickupSlot, useFarmerMarkets, usePublicMarketsForJoin, useRemoveFarmerMarket, useTogglePickupSlot, useUpdateFarmerMarketStall } from '../../features/farmer/hooks/useFarmerMarkets';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Switch } from '../../components/ui/Switch';
import '../../styles/farmer/FarmerMarketsPage.css';
L.Icon.Default.mergeOptions({
    iconRetinaUrl: markerIcon2x,
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
});
const WEEKDAYS = [
    { value: 1, label: 'Mon' },
    { value: 2, label: 'Tue' },
    { value: 3, label: 'Wed' },
    { value: 4, label: 'Thu' },
    { value: 5, label: 'Fri' },
    { value: 6, label: 'Sat' },
    { value: 7, label: 'Sun' },
];
export default function FarmerMarketsPage() {
    const marketsQuery = useFarmerMarkets();
    const publicMarketsQuery = usePublicMarketsForJoin();
    const [selectedId, setSelectedId] = useState(null);
    const [addMarketId, setAddMarketId] = useState('');
    const [stallLabel, setStallLabel] = useState('');
    const [editStall, setEditStall] = useState('');
    const selected = useMemo(() => marketsQuery.data?.find((m) => m.id === selectedId) ?? null, [marketsQuery.data, selectedId]);
    const addMutation = useAddFarmerMarket();
    const updateStallMutation = useUpdateFarmerMarketStall();
    const removeMutation = useRemoveFarmerMarket();
    const addSlotMutation = useCreatePickupSlot();
    const toggleSlotMutation = useTogglePickupSlot();
    if (marketsQuery.isLoading)
        return <PageSkeleton />;
    const publicList = publicMarketsQuery.data?.results ?? [];
    const joinedIds = new Set(marketsQuery.data?.map((m) => m.market.id) ?? []);
    const availableToJoin = publicList.filter((m) => !joinedIds.has(m.id));
    const selectMarket = (membershipId, label) => {
        setSelectedId(membershipId);
        setEditStall(label);
    };
    return (<div className="farmer-markets-page">
      <PageHeader title="Markets & pickup times" description="Join markets, set your stall label, and publish bookable pickup slots."/>

      <div className="page-primitive__layout-5">
        <div className="page-primitive__layout-5-side">
          {!marketsQuery.data?.length ? (<EmptyState title="You have not joined a market yet" description="Join a market session to start receiving pre-orders."/>) : (marketsQuery.data.map((m) => (<button key={m.id} type="button" onClick={() => selectMarket(m.id, m.stall_label)} className={selectedId === m.id
                ? 'farmer-markets-page__market-btn farmer-markets-page__market-btn--selected'
                : 'farmer-markets-page__market-btn'}>
                <p className="page-primitive__semibold">{m.market.name}</p>
                <p className="page-primitive__muted-sm">{m.stall_label}</p>
              </button>)))}

          <div className="page-primitive__dashed-panel">
            <p className="page-primitive__font-medium">Add market</p>
            <select className="page-primitive__select-full" value={addMarketId} onChange={(e) => setAddMarketId(e.target.value)}>
              <option value="">Select marketâ€¦</option>
              {availableToJoin.map((m) => (<option key={m.id} value={String(m.id)}>
                  {m.name}
                </option>))}
            </select>
            <Input label="Stall label (e.g. Aisle A Â· Stall 12)" value={stallLabel} onChange={(e) => setStallLabel(e.target.value)}/>
            <Button data-write className="page-primitive__btn-full" disabled={!addMarketId} loading={addMutation.isPending} onClick={() => {
            const marketId = Number(addMarketId);
            if (!Number.isFinite(marketId))
                return;
            addMutation.mutate({
                market_id: marketId,
                stall_label: stallLabel || 'New stall',
            }, {
                onSuccess: (data) => {
                    setSelectedId(data.id);
                    setAddMarketId('');
                    setStallLabel('');
                    setEditStall(data.stall_label);
                },
            });
        }}>
              Add market
            </Button>
          </div>
        </div>

        <div className="page-primitive__layout-5-main">
          {!selected ? (<EmptyState title="Select a market to set up pickup times"/>) : (<>
              <div className="page-primitive__form-field">
                <div className="page-primitive__inline-row">
                  <Input label="Stall label" value={editStall} onChange={(e) => setEditStall(e.target.value)}/>
                  <Button data-write loading={updateStallMutation.isPending} onClick={() => updateStallMutation.mutate({
                farmerMarketId: selected.id,
                stall_label: editStall,
            })}>
                    Save
                  </Button>
                </div>
              </div>

              <div className="page-primitive__map-h-64">
                <MapContainer center={[selected.market.latitude, selected.market.longitude]} zoom={16} className="page-primitive__map-fill">
                  <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
                  <Marker position={[selected.market.latitude, selected.market.longitude]}/>
                </MapContainer>
              </div>

              <div>
                <div className="farmer-markets-page__slots-head">
                  <h3 className="page-primitive__heading">Weekly pickup slots</h3>
                </div>
                <div className="page-primitive__actions-row farmer-markets-page__slots-actions">
                  {WEEKDAYS.map((d) => (<Button key={d.value} size="sm" variant="outline" data-write onClick={() => addSlotMutation.mutate({
                    farmer_market_id: selected.id,
                    day_of_week: d.value,
                    start_time: '06:00',
                    end_time: '08:00',
                })}>
                      + {d.label}
                    </Button>))}
                </div>
                <div className="page-primitive__stack-2">
                  {selected.slots.length === 0 ? (<p className="page-primitive__muted-sm">No pickup slots yet.</p>) : (selected.slots.map((slot) => {
                const day = WEEKDAYS.find((d) => d.value === slot.day_of_week)?.label ??
                    String(slot.day_of_week);
                return (<div key={slot.id} className="page-primitive__list-item-row">
                          <span>
                            {day} Â· {slot.start_time}â€“{slot.end_time}
                          </span>
                          <Switch checked={slot.is_active} onCheckedChange={(checked) => toggleSlotMutation.mutate({
                        slotId: slot.id,
                        is_active: checked,
                    })}/>
                        </div>);
            }))}
                </div>
              </div>

              <Button variant="destructive" data-write loading={removeMutation.isPending} onClick={() => removeMutation.mutate(selected.id, {
                onSuccess: () => setSelectedId(null),
            })}>
                Leave market
              </Button>
            </>)}
        </div>
      </div>
    </div>);
}

