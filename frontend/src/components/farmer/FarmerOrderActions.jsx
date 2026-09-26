import { useState } from 'react';
import PropTypes from 'prop-types';
import { toast } from 'sonner';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { Button } from '../ui/Button';
import { Textarea } from '../ui/Textarea';
import { useFarmerOrderActions } from '../../features/farmer/hooks/useFarmerOrderActions';
import '../../styles/farmer/FarmerOrderActions.css';
export function FarmerOrderActions({ order, size = 'sm' }) {
    const { run } = useFarmerOrderActions(order);
    const [declineOpen, setDeclineOpen] = useState(false);
    const [reason, setReason] = useState('');
    const [confirmAction, setConfirmAction] = useState(null);
    const afterSuccess = () => {
        setDeclineOpen(false);
        setConfirmAction(null);
        setReason('');
    };
    const mutate = (action) => {
        run.mutate({ action, reason }, {
            onSuccess: () => {
                afterSuccess();
            },
        });
    };
    const renderBtn = (action, label, variant = 'default') => {
        if (!order.allowed_actions.includes(action))
            return null;
        return (<span key={action}>
        <Button size={size} variant={variant} data-write disabled={run.isPending} loading={run.isPending &&
                (confirmAction === action || (action === 'DECLINE' && declineOpen))} onClick={() => {
                if (action === 'DECLINE') {
                    setDeclineOpen(true);
                    return;
                }
                setConfirmAction(action);
            }}>
          {label}
        </Button>
      </span>);
    };
    return (<>
      <div className="farmer-order-actions">
        {renderBtn('ACCEPT', 'Accept', 'default')}
        {renderBtn('DECLINE', 'Decline', 'destructive')}
        {renderBtn('READY', 'Ready', 'accent')}
        {renderBtn('COMPLETE', 'Complete', 'default')}
        {renderBtn('NO_SHOW', 'No-show', 'outline')}
      </div>

      <ConfirmDialog open={declineOpen} onOpenChange={setDeclineOpen} title="Decline order" description="Tell the shopper why (5â€“500 characters)." confirmLabel="Decline" destructive loading={run.isPending} onConfirm={() => {
            if (reason.trim().length < 5) {
                toast.error('Reason must be at least 5 characters');
                return;
            }
            mutate('DECLINE');
        }}>
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason for decliningâ€¦" className="farmer-order-actions__reason"/>
      </ConfirmDialog>

      <ConfirmDialog open={confirmAction !== null && confirmAction !== 'DECLINE'} onOpenChange={(open) => {
            if (!open)
                setConfirmAction(null);
        }} title={confirmAction === 'ACCEPT'
            ? 'Accept this pre-order?'
            : confirmAction === 'READY'
                ? 'Mark ready for pickup?'
                : confirmAction === 'COMPLETE'
                    ? 'Mark this pickup as complete?'
                    : 'Mark customer as no-show?'} loading={run.isPending} destructive={confirmAction === 'NO_SHOW'} onConfirm={() => {
            if (confirmAction)
                mutate(confirmAction);
        }}/>
    </>);
}

FarmerOrderActions.propTypes = {
    order: PropTypes.object.isRequired,
    size: PropTypes.oneOf(['default', 'sm', 'lg', 'icon']),
};

