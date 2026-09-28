import PropTypes from 'prop-types';

import { dayOfWeekLabel } from '../../utils/labels';
import '../../styles/farmer/MarketChecklist.css';

export function isSellingMarket(farmerMarket) {
  return farmerMarket.status === 'APPROVED' && farmerMarket.is_market_active;
}

function noteFor(farmerMarket) {
  if (farmerMarket.status !== 'APPROVED') return 'Waiting for approval';
  if (!farmerMarket.is_market_active) return 'Closed by admin';
  const days = [...new Set(farmerMarket.slots.filter((slot) => slot.is_active).map((slot) => slot.day_of_week))]
    .sort((a, b) => a - b)
    .map((day) => dayOfWeekLabel(day, { short: true }));
  return days.length ? `Pickup ${days.join(', ')}` : 'No pickup times yet';
}

export function MarketChecklist({ markets, value, onChange, disabled = false }) {
  const toggle = (marketId) =>
    onChange(value.includes(marketId) ? value.filter((id) => id !== marketId) : [...value, marketId]);

  return (
    <ul className="market-checklist">
      {markets.map((farmerMarket) => {
        const selling = isSellingMarket(farmerMarket);
        const checked = selling && value.includes(farmerMarket.market.id);
        return (
          <li key={farmerMarket.id}>
            <label className={`market-checklist__item${selling ? '' : ' market-checklist__item--off'}`}>
              <input
                type="checkbox"
                className="market-checklist__box"
                checked={checked}
                disabled={disabled || !selling}
                onChange={() => toggle(farmerMarket.market.id)}
              />
              <span className="market-checklist__text">
                <span className="market-checklist__name">{farmerMarket.market.name}</span>
                <span className="market-checklist__meta">
                  {farmerMarket.stall_label} · {noteFor(farmerMarket)}
                </span>
              </span>
            </label>
          </li>
        );
      })}
    </ul>
  );
}

MarketChecklist.propTypes = {
  markets: PropTypes.arrayOf(PropTypes.object).isRequired,
  value: PropTypes.arrayOf(PropTypes.number).isRequired,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
};
