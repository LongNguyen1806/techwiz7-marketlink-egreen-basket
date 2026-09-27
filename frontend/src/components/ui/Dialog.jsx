import * as DialogPrimitive from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { cn } from '../../lib/cn';
import '../../styles/common/Dialog.css';
export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;
export const DialogPortal = DialogPrimitive.Portal;
export function DialogOverlay({ className, ...props }) {
    return (<DialogPrimitive.Overlay className={cn('dialog-overlay', className)} {...props}/>);
}
export function DialogContent({ className, children, ...props }) {
    return (<DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content className={cn('dialog-content', className)} {...props}>
        {children}
        <DialogPrimitive.Close className="dialog__close">
          <X className="dialog__close-icon"/>
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPortal>);
}
export function DialogHeader({ className, ...props }) {
    return <div className={cn('dialog-header', className)} {...props}/>;
}
export function DialogTitle({ className, ...props }) {
    return <DialogPrimitive.Title className={cn('dialog-title', className)} {...props}/>;
}
export function DialogDescription({ className, ...props }) {
    return (<DialogPrimitive.Description className={cn('dialog-description', className)} {...props}/>);
}

