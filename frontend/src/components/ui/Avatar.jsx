import * as AvatarPrimitive from '@radix-ui/react-avatar';
import { cn } from '../../lib/cn';
import '../../styles/common/Avatar.css';
export function Avatar({ className, ...props }) {
    return <AvatarPrimitive.Root className={cn('avatar', className)} {...props}/>;
}
export function AvatarImage({ className, ...props }) {
    return <AvatarPrimitive.Image className={cn('avatar__image', className)} {...props}/>;
}
export function AvatarFallback({ className, ...props }) {
    return (<AvatarPrimitive.Fallback className={cn('avatar__fallback', className)} {...props}/>);
}

