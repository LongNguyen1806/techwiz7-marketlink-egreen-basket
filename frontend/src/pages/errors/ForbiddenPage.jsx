import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/Button';
import { ROUTES } from '../../constants/routes';
import '../../styles/errors/ForbiddenPage.css';

export default function ForbiddenPage() {
  return (
    <div className="forbidden-page">
      <p className="forbidden-page__code">403</p>
      <h1 className="forbidden-page__title">You do not have access</h1>
      <p className="forbidden-page__desc">This area is limited to another account type or permission level.</p>
      <Button asChild>
        <Link to={ROUTES.HOME}>Back to MarketLink home</Link>
      </Button>
    </div>
  );
}
