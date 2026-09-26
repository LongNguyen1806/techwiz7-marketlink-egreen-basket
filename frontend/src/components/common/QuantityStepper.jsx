import PropTypes from 'prop-types';
import { Minus, Plus } from 'lucide-react';
import { Button } from '../ui/Button';
import { cn } from '../../lib/cn';
import '../../styles/common/QuantityStepper.css';
export function QuantityStepper({ value, min = 1, max = 99, onChange, className, disabled = false, }) {
    return (<div className={cn('quantity-stepper', className)}>
      <Button type="button" variant="outline" size="icon" className="quantity-stepper__btn" disabled={disabled || value <= min} aria-label="Decrease quantity" onClick={() => onChange(Math.max(min, value - 1))}>
        <Minus className="quantity-stepper__icon"/>
      </Button>
      <span className="quantity-stepper__value">{value}</span>
      <Button type="button" variant="outline" size="icon" className="quantity-stepper__btn" disabled={disabled || value >= max} aria-label="Increase quantity" onClick={() => onChange(Math.min(max, value + 1))}>
        <Plus className="quantity-stepper__icon"/>
      </Button>
    </div>);
}

QuantityStepper.propTypes = {
    value: PropTypes.number.isRequired,
    min: PropTypes.number,
    max: PropTypes.number,
    onChange: PropTypes.func.isRequired,
    className: PropTypes.string,
    disabled: PropTypes.bool,
};

