import PropTypes from 'prop-types';
import { formatMoney } from '../../../utils/formatters';
import './OrderItemsTable.css';

/**
 * The lines of an order (C-05). Prices are the snapshot taken when the order was placed, which is why
 * they can differ from the catalogue: what was agreed is what will be paid.
 *
 * The total sits outside the table on purpose — it is the order's `total_amount` from the server, not
 * a sum this screen computed.
 */
export function OrderItemsTable({ items, totalAmount }) {
  return (
    <div className="order-items">
      <table className="order-items__table" aria-label="Items in this order">
        <thead>
          <tr>
            <th scope="col" className="order-items__th">Product</th>
            <th scope="col" className="order-items__th">Unit price</th>
            <th scope="col" className="order-items__th">Quantity</th>
            <th scope="col" className="order-items__th order-items__th--end">Line total</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="order-items__row">
              <td className="order-items__td">{item.product_name}</td>
              <td className="order-items__td">{formatMoney(item.unit_price)}</td>
              <td className="order-items__td">{`${item.quantity} ${item.unit}`}</td>
              <td className="order-items__td order-items__td--end">{formatMoney(item.line_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="order-items__total">
        <span>Total</span>
        <span className="order-items__total-value">{formatMoney(totalAmount)}</span>
      </p>
      <p className="order-items__note">Pay on pickup — cash at the stall.</p>
    </div>
  );
}

OrderItemsTable.propTypes = {
  items: PropTypes.array.isRequired,
  totalAmount: PropTypes.string.isRequired,
};
