import PropTypes from 'prop-types';
import { Suspense } from 'react';
import { PageSkeleton } from '../components/feedback/PageSkeleton';
export function Suspend({ children }) {
    return <Suspense fallback={<PageSkeleton />}>{children}</Suspense>;
}

Suspend.propTypes = {
    children: PropTypes.node,
};
