import { Link, useParams } from 'react-router-dom';
import { MapContainer, Marker, TileLayer } from 'react-leaflet';
import { OSM_ATTRIBUTION, OSM_TILE_URL } from '../../lib/map';

import { useAdminMarket } from '../../hooks/queries/admin/useAdminMarkets';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/Card';
import '../../styles/admin/AdminMarketDetailPage.css';

const DAY_LABELS = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function Row({ label, children }) {
  return (
    <div className="admin-market-detail__row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

// Looking at a market is not editing it: this page only reads, and Edit is its own button.
export default function AdminMarketDetailPage() {
  const { id } = useParams();
  const marketId = Number(id);
  const query = useAdminMarket(marketId);
  const market = query.data;

  if (query.isLoading) return <PageSkeleton />;
  if (query.isError || !market) {
    return (
      <EmptyState
        title="Market couldn't be loaded"
        actionLabel="Try again"
        onAction={() => query.refetch()}
      />
    );
  }

  const days = market.operating_days.map((day) => DAY_LABELS[day]).join(', ');
  const closures = market.upcoming_closures ?? [];

  return (
    <div className="admin-market-detail">
      <PageHeader
        title={market.name}
        description={market.address}
        actions={
          <div className="admin-market-detail__actions">
            <Button asChild variant="outline">
              <Link to="/admin/markets">Back to markets</Link>
            </Button>
            <Button asChild>
              <Link to={`/admin/markets/${market.id}/edit`}>Edit</Link>
            </Button>
          </div>
        }
      />

      <div className="admin-market-detail__body">
        <Card>
          <CardHeader className="admin-market-detail__card-head">
            <CardTitle>Details</CardTitle>
            <Badge variant={market.is_active ? 'success' : 'secondary'}>
              {market.is_active ? 'Open' : 'Closed'}
            </Badge>
          </CardHeader>
          <CardContent>
            <dl className="admin-market-detail__list">
              <Row label="Market days">{days || '—'}</Row>
              <Row label="Hours">
                {market.open_time}–{market.close_time}
              </Row>
              <Row label="Stalls">{market.farmer_count}</Row>
              <Row label="Open orders">{market.open_order_count}</Row>
              <Row label="Description">
                {market.description ? (
                  <span className="admin-market-detail__text">{market.description}</span>
                ) : (
                  <span className="page-primitive__muted-sm">No description yet.</span>
                )}
              </Row>
              <Row label="Upcoming closures">
                {closures.length === 0 ? (
                  <span className="page-primitive__muted-sm">None planned.</span>
                ) : (
                  <ul className="admin-market-detail__closures">
                    {closures.map((closure) => (
                      <li key={closure.id}>
                        {closure.start_date} → {closure.end_date}
                        {closure.reason ? ` · ${closure.reason}` : ''}
                      </li>
                    ))}
                  </ul>
                )}
              </Row>
            </dl>
          </CardContent>
        </Card>

        <div className="admin-market-detail__map page-primitive__map-box">
          <MapContainer
            center={[market.latitude, market.longitude]}
            zoom={15}
            className="page-primitive__map-fill"
            scrollWheelZoom={false}
          >
            <TileLayer url={OSM_TILE_URL} attribution={OSM_ATTRIBUTION} />
            <Marker position={[market.latitude, market.longitude]} />
          </MapContainer>
        </div>
      </div>
    </div>
  );
}
