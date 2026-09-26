import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { FarmerOrderActions } from '../../components/farmer/FarmerOrderActions';
import { Button } from '../../components/ui/Button';
import { ROUTES } from '../../constants/routes';
import { useApplyWeeklyTemplate, useWeeklyTemplatePreview } from '../../hooks/queries/farmer/useFarmerProducts';
import { formatPickupWindow } from '../../utils/formatters';
import '../../styles/farmer/FarmerStockTemplatePage.css';

export default function FarmerStockTemplatePage() {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const previewQuery = useWeeklyTemplatePreview();
  const apply = useApplyWeeklyTemplate();

  if (previewQuery.isPending) return <PageSkeleton />;
  if (!previewQuery.data) {
    return (
      <EmptyState title="Stock template couldn't be loaded" actionLabel="Try again" onAction={() => previewQuery.refetch()} />
    );
  }

  const { rows, overdue_orders: overdueOrders } = previewQuery.data;
  // Products without a weekly default keep their stock, so only these are reset.
  const templated = rows.filter((row) => row.weekly_default_quantity !== null);

  return (
    <div className="farmer-stock-template-page">
      <PageHeader
        title="Weekly stock reset"
        description="Preview current vs default stock, then apply the weekly template."
        actions={
          <Button data-write disabled={templated.length === 0} onClick={() => setConfirmOpen(true)}>
            Apply weekly template
          </Button>
        }
      />

      {overdueOrders.length > 0 ? (
        <div className="page-primitive__warn-panel">
          <p className="page-primitive__semibold">
            {overdueOrders.length} order{overdueOrders.length === 1 ? ' is' : 's are'} past pickup and still open
          </p>
          <p className="page-primitive__muted-sm">Close them first so the new stock reflects what was really collected.</p>
          <ul className="page-primitive__warn-list page-primitive__list-plain">
            {overdueOrders.map((order) => (
              <li key={order.id} className="page-primitive__list-item-row">
                <Link className="page-primitive__link-underline" to={ROUTES.FARMER.ORDER(order.id)}>
                  #{order.id} · {order.customer.full_name} ·{' '}
                  {formatPickupWindow(order.pickup_start_at, order.pickup_end_at)}
                </Link>
                <FarmerOrderActions order={order} />
              </li>
            ))}
          </ul>
          <Button asChild size="sm" className="page-primitive__mt-3" variant="outline">
            <Link to={`${ROUTES.FARMER.ORDERS}?tab=overdue`}>Handle overdue orders</Link>
          </Button>
        </div>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState title="No products yet" description="Add produce and give it a weekly default to use the reset." />
      ) : (
        <div className="page-primitive__table-wrap" aria-busy={previewQuery.isFetching}>
          <table className="page-primitive__table">
            <thead className="page-primitive__table-head">
              <tr>
                <th className="page-primitive__table-th">Product</th>
                <th className="page-primitive__table-th">Current stock</th>
                <th className="page-primitive__table-th">New stock</th>
                <th className="page-primitive__table-th">Held</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.product_id} className="page-primitive__table-row">
                  <td className="page-primitive__table-td page-primitive__font-medium">
                    {row.name}
                    {!row.is_available ? <p className="page-primitive__muted-xs">Paused, stays paused</p> : null}
                  </td>
                  <td className="page-primitive__table-td">{row.current_stock}</td>
                  <td className="page-primitive__table-td page-primitive__primary-emphasis">
                    {row.weekly_default_quantity === null ? (
                      <span className="page-primitive__muted-xs">No weekly default</span>
                    ) : (
                      row.new_stock
                    )}
                  </td>
                  <td className="page-primitive__table-td">{row.held_quantity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Apply weekly stock reset?"
        description={`Stock for ${templated.length} product${templated.length === 1 ? '' : 's'} becomes its weekly default minus what open orders already hold.`}
        confirmLabel="Confirm and apply"
        loading={apply.isPending}
        onConfirm={() => apply.mutate(undefined, { onSuccess: () => setConfirmOpen(false) })}
      />
    </div>
  );
}
