import { useMemo } from 'react';
import PropTypes from 'prop-types';
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';

import { useDebouncedValue } from '../../hooks/common/useDebouncedValue';
import { useProductPrecheck } from '../../hooks/queries/farmer/useFarmerProducts';
import { cn } from '../../lib/cn';
import '../../styles/farmer/ListingPrecheck.css';

const PRICE_PATTERN = /^\d{1,5}(\.\d{1,2})?$/;
const PRECHECK_DELAY_MS = 500;

const SEVERITY = {
  HIGH: { icon: AlertTriangle, tone: 'high' },
  MEDIUM: { icon: AlertTriangle, tone: 'medium' },
  LOW: { icon: Info, tone: 'low' },
};

/** Only the values that are complete enough to check; the API validates them again. */
function toParams(values, productId) {
  const name = (values.name ?? '').trim();
  const price = String(values.price ?? '').trim();
  if (!name && !price) return null;
  const params = { name, description: (values.description ?? '').trim(), unit: values.unit };
  if (productId) params.product_id = productId;
  if (values.category_id > 0) params.category_id = values.category_id;
  if (PRICE_PATTERN.test(price) && Number(price) >= 0.01) params.price = price;
  if (Number.isInteger(values.stock_quantity) && values.stock_quantity >= 0) params.stock_quantity = values.stock_quantity;
  if (Number.isInteger(values.min_per_order) && values.min_per_order >= 1) params.min_per_order = values.min_per_order;
  if (Number.isInteger(values.max_per_order) && values.max_per_order >= 1) params.max_per_order = values.max_per_order;
  return params;
}

/**
 * "Before you send it": the same rule checks the admin's review runs, on the form as the farmer
 * types. Advice only; saving is never blocked, and an administrator still reviews every listing.
 */
export function ListingPrecheck({ values, productId }) {
  // A string key: the form hands over a new object every render, the text only changes on edits.
  const key = JSON.stringify(toParams(values, productId));
  const debouncedKey = useDebouncedValue(key, PRECHECK_DELAY_MS);
  const params = useMemo(() => JSON.parse(debouncedKey), [debouncedKey]);
  const query = useProductPrecheck(params);

  if (!params) return null;
  const findings = query.data?.findings ?? [];
  const settling = key !== debouncedKey || query.isFetching;

  return (
    <section className="listing-precheck" aria-live="polite" aria-labelledby="listing-precheck-title">
      <h2 className="listing-precheck__title" id="listing-precheck-title">
        Before you send it
        {settling ? <span className="listing-precheck__status">checking…</span> : null}
      </h2>
      {query.data && findings.length === 0 ? (
        <p className="listing-precheck__ok">
          <CheckCircle2 aria-hidden className="listing-precheck__icon" />
          Nothing stands out. An administrator reviews every new listing before shoppers see it.
        </p>
      ) : null}
      {findings.length ? (
        <>
          <ul className="listing-precheck__list">
            {findings.map((finding, index) => {
              const { icon: Icon, tone } = SEVERITY[finding.severity] ?? SEVERITY.LOW;
              return (
                <li key={`${finding.check}-${index}`} className={cn('listing-precheck__item', `listing-precheck__item--${tone}`)}>
                  <Icon aria-hidden className="listing-precheck__icon" />
                  <span>{finding.message}</span>
                </li>
              );
            })}
          </ul>
          <p className="listing-precheck__hint">
            You can still save. Fixing these first gets your listing approved faster.
          </p>
        </>
      ) : null}
    </section>
  );
}

ListingPrecheck.propTypes = {
  values: PropTypes.object.isRequired,
  productId: PropTypes.number,
};
