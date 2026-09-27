import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { cn } from '../../lib/cn';
import '../../styles/common/DropdownMenu.css';
export const DropdownMenu = DropdownMenuPrimitive.Root;
export const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;
export const DropdownMenuGroup = DropdownMenuPrimitive.Group;
export const DropdownMenuPortal = DropdownMenuPrimitive.Portal;
export function DropdownMenuContent({ className, sideOffset = 8, ...props }) {
    return (<DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content sideOffset={sideOffset} className={cn('dropdown-menu', className)} {...props}/>
    </DropdownMenuPrimitive.Portal>);
}
export function DropdownMenuItem({ className, ...props }) {
    return (<DropdownMenuPrimitive.Item className={cn('dropdown-menu__item', className)} {...props}/>);
}
export function DropdownMenuLabel({ className, ...props }) {
    return (<DropdownMenuPrimitive.Label className={cn('dropdown-menu__label', className)} {...props}/>);
}
export function DropdownMenuSeparator({ className, ...props }) {
    return (<DropdownMenuPrimitive.Separator className={cn('dropdown-menu__separator', className)} {...props}/>);
}

