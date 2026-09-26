import PropTypes from 'prop-types';
import { formatMoney } from '../../utils/formatters';
import { cn } from '../../lib/cn';
import '../../styles/common/PriceTag.css';
export function PriceTag({ amount, unit, className, }) {
    return (<span className={cn('price-tag', className)}>
      {formatMoney(amount)}
      {unit ? <span className="price-tag__unit">/{unit}</span> : null}
    </span>);
}

PriceTag.propTypes = {
    amount: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
    unit: PropTypes.string,
    className: PropTypes.string,
};

