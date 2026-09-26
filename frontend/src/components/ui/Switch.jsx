import * as SwitchPrimitives from '@radix-ui/react-switch';
import { cn } from '../../lib/cn';
import '../../styles/common/Switch.css';
export function Switch({ className, ...props }) {
    return (<SwitchPrimitives.Root className={cn('switch', className)} {...props}>
      <SwitchPrimitives.Thumb className="switch__thumb"/>
    </SwitchPrimitives.Root>);
}

