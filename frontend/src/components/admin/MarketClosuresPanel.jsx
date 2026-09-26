import { useState } from 'react';
import { toast } from 'sonner';

import {
  useCreateMarketClosure,
  useDeleteMarketClosure,
  useMarketClosures,
} from '../../hooks/queries/admin/useAdminMarkets';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Label } from '../ui/Label';

import '../../styles/admin/MarketClosuresPanel.css';

const REASON_MAX_LENGTH = 200;

function today() {
  return new Date().toISOString().slice(0, 10);
}

function formatRange(startDate, endDate) {
  return startDate === endDate ? startDate : `${startDate} → ${endDate}`;
}

export function MarketClosuresPanel({ marketId }) {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [reason, setReason] = useState('');

  const closures = useMarketClosures(marketId, true);
  const create = useCreateMarketClosure(marketId);
  const remove = useDeleteMarketClosure(marketId);

  const reset = () => {
    setStartDate('');
    setEndDate('');
    setReason('');
  };

  const submit = () => {
    if (!startDate || !endDate) {
      toast.error('Pick both a start and an end date');
      return;
    }
    if (endDate < startDate) {
      toast.error('The end date cannot be earlier than the start date');
      return;
    }
    create.mutate(
      {
        start_date: startDate,
        end_date: endDate,
        reason: reason.trim() || undefined,
      },
      { onSuccess: reset },
    );
  };

  const rows = closures.data ?? [];

  return (
    <section className="market-closures">
      <div className="market-closures__head">
        <Label>Temporary closures</Label>
        <p className="page-primitive__muted-xs">
          Shoppers cannot pick a collection day inside a closure period.
        </p>
      </div>

      {closures.isLoading ? (
        <p className="page-primitive__muted-xs">Loading closures…</p>
      ) : rows.length === 0 ? (
        <p className="page-primitive__muted-xs">No closure periods yet.</p>
      ) : (
        <ul className="market-closures__list">
          {rows.map((closure) => (
            <li key={closure.id} className="market-closures__item">
              <div>
                <p className="market-closures__range">
                  {formatRange(closure.start_date, closure.end_date)}
                </p>
                {closure.reason ? (
                  <p className="page-primitive__muted-xs">{closure.reason}</p>
                ) : null}
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                loading={remove.isPending}
                onClick={() => remove.mutate(closure.id)}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="market-closures__form">
        <div className="page-primitive__form-field">
          <Input
            id="closure_start"
            type="date"
            label="From"
            min={today()}
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
        </div>
        <div className="page-primitive__form-field">
          <Input
            id="closure_end"
            type="date"
            label="To"
            min={startDate || today()}
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </div>
        <div className="page-primitive__form-field market-closures__reason">
          <Input
            id="closure_reason"
            label="Reason"
            maxLength={REASON_MAX_LENGTH}
            placeholder="Lunar New Year closure"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
        <Button type="button" onClick={submit} loading={create.isPending}>
          Add
        </Button>
      </div>
    </section>
  );
}

export default MarketClosuresPanel;
