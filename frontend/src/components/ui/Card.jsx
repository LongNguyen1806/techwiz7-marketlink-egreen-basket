import PropTypes from 'prop-types';
import { cn } from '../../lib/cn';
import '../../styles/common/Card.css';
export function Card({ className, ...props }) {
    return <div className={cn('card', className)} {...props}/>;
}
export function CardHeader({ className, ...props }) {
    return <div className={cn('card__header', className)} {...props}/>;
}
export function CardTitle({ className, ...props }) {
    return <h3 className={cn('card__title', className)} {...props}/>;
}
export function CardDescription({ className, ...props }) {
    return <p className={cn('card__description', className)} {...props}/>;
}
export function CardContent({ className, ...props }) {
    return <div className={cn('card__content', className)} {...props}/>;
}

const cardPartPropTypes = {
    className: PropTypes.string,
    children: PropTypes.node,
};

Card.propTypes = cardPartPropTypes;
CardHeader.propTypes = cardPartPropTypes;
CardTitle.propTypes = cardPartPropTypes;
CardDescription.propTypes = cardPartPropTypes;
CardContent.propTypes = cardPartPropTypes;

