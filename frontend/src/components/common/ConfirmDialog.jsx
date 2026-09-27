import PropTypes from 'prop-types';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/Dialog';
import { Button } from '../ui/Button';
import '../../styles/common/ConfirmDialog.css';
// confirmDisabled keeps the confirm button shut until the dialog's own conditions are met - a
// reason long enough to act on, or the word "confirm" typed before closing a market. Without
// it those checks are decoration and the button fires on the first click.
export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel = 'Confirm', cancelLabel = 'Cancel', loading = false, destructive = false, confirmDisabled = false, onConfirm, children, }) {
    return (<Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        {children}
        <div className="confirm-dialog__actions">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button variant={destructive ? 'destructive' : 'default'} loading={loading} disabled={confirmDisabled} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>);
}

ConfirmDialog.propTypes = {
    open: PropTypes.bool.isRequired,
    onOpenChange: PropTypes.func.isRequired,
    title: PropTypes.string.isRequired,
    description: PropTypes.string,
    confirmLabel: PropTypes.string,
    cancelLabel: PropTypes.string,
    loading: PropTypes.bool,
    destructive: PropTypes.bool,
    confirmDisabled: PropTypes.bool,
    onConfirm: PropTypes.func.isRequired,
    children: PropTypes.node,
};

