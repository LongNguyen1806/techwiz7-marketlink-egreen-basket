import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { ROUTES } from '../../constants/routes';
import '../../styles/errors/NotFoundPage.css';

export default function NotFoundPage() {
  return (
    <div className="not-found-page">
      <p className="not-found-page__code">404</p>
      <h1 className="not-found-page__title">We lost that page</h1>
      <p className="not-found-page__desc">The link may be outdated, or the page may have moved.</p>
      <Button asChild>
        <Link to={ROUTES.HOME}>Back to MarketLink home</Link>
      </Button>
    </div>
  );
}
