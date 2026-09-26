import { Skeleton } from '../ui/Skeleton';
import '../../styles/common/PageSkeleton.css';
export function PageSkeleton() {
    return (<div className="page-skeleton" aria-busy aria-label="Loading">
      <div className="page-skeleton__header">
        <Skeleton className="page-skeleton__title"/>
        <Skeleton className="page-skeleton__subtitle"/>
      </div>
      <div className="page-skeleton__grid">
        {Array.from({ length: 4 }).map((_, i) => (<Skeleton key={i} className="page-skeleton__card"/>))}
      </div>
      <Skeleton className="page-skeleton__block"/>
    </div>);
}

