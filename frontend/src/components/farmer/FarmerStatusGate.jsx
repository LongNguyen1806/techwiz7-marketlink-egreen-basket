import PropTypes from 'prop-types';
import { AlertTriangle, Ban, Clock } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/Tooltip';
import { cn } from '../../lib/cn';
import '../../styles/farmer/FarmerStatusGate.css';
export function FarmerStatusGate({ status, rejectionReason, children, className, }) {
    const isWriteLocked = status === 'PENDING' || status === 'REJECTED' || status === 'SUSPENDED';
    return (<div className={cn('farmer-status-gate', className)}>
      {status === 'PENDING' ? (<div className="farmer-status-gate__alert farmer-status-gate__alert--pending">
          <Clock className="farmer-status-gate__icon"/>
          <div>
            <p className="farmer-status-gate__title">Waiting for approval</p>
            <p className="farmer-status-gate__desc">
              You can browse the workspace, but listing produce is unlocked after
              an admin reviews your stall.
            </p>
          </div>
          <Badge variant="warning">Pending</Badge>
        </div>) : null}

      {status === 'REJECTED' ? (<div className="farmer-status-gate__alert farmer-status-gate__alert--danger">
          <AlertTriangle className="farmer-status-gate__icon"/>
          <div>
            <p className="farmer-status-gate__title">Stall application declined</p>
            <p className="farmer-status-gate__desc">
              {rejectionReason || 'Update your profile details and resubmit for review.'}
            </p>
          </div>
        </div>) : null}

      {status === 'SUSPENDED' ? (<div className="farmer-status-gate__alert farmer-status-gate__alert--danger">
          <Ban className="farmer-status-gate__icon"/>
          <div>
            <p className="farmer-status-gate__title">Stall temporarily suspended</p>
            <p className="farmer-status-gate__desc">
              Editing and new listings are paused. You can still review existing data.
            </p>
          </div>
        </div>) : null}

      <TooltipProvider>
        <div className={cn('farmer-status-gate__content', isWriteLocked && 'is-write-locked')}>
          {isWriteLocked ? (<Tooltip>
              <TooltipTrigger asChild>
                <div>{children}</div>
              </TooltipTrigger>
              <TooltipContent>
                Cannot perform this action while profile is{' '}
                {status === 'PENDING'
                ? 'pending approval'
                : status === 'REJECTED'
                    ? 'rejected'
                    : 'suspended'}
              </TooltipContent>
            </Tooltip>) : (children)}
        </div>
      </TooltipProvider>
    </div>);
}

FarmerStatusGate.propTypes = {
    status: PropTypes.oneOf(['PENDING', 'APPROVED', 'REJECTED', 'SUSPENDED']).isRequired,
    rejectionReason: PropTypes.string,
    children: PropTypes.node,
    className: PropTypes.string,
};

