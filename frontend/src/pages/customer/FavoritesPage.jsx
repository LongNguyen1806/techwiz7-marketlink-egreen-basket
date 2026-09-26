import { useState } from 'react';
import PropTypes from 'prop-types';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { Button } from '../../components/ui/Button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs';
import { FarmerCard } from '../../components/common/cards/FarmerCard';
import { MarketCard } from '../../components/common/cards/MarketCard';
import { ProductCard } from '../../components/common/cards/ProductCard';
import { useFavoriteList } from '../../hooks/queries/customer/useFavorites';
import '../../styles/customer/FavoritesPage.css';


function FavoriteList({ kind, render }) {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useFavoriteList(kind, page);

  if (isLoading) return <PageSkeleton />;

  const rows = data?.results ?? [];
  if (rows.length === 0) {
    return <p className="favorites-page__empty">Nothing saved here yet.</p>;
  }

  return (
    <>
      <div className="favorites-page__grid">{rows.map(render)}</div>
      {data.total_pages > 1 ? (
        <div className="favorites-page__pager">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={data.previous === null}
            onClick={() => setPage(data.previous)}
          >
            Previous
          </Button>
          <p className="favorites-page__pager-text">{`Page ${data.page} of ${data.total_pages}`}</p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={data.next === null}
            onClick={() => setPage(data.next)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </>
  );
}

FavoriteList.propTypes = {
  kind: PropTypes.oneOf(['farmers', 'products', 'markets']).isRequired,
  render: PropTypes.func.isRequired,
};

export default function FavoritesPage() {
  return (
    <section className="favorites-page">
      <PageHeader title="Favorites" description="The stalls, products and markets you saved." />

      <Tabs defaultValue="farmers">
        <TabsList>
          <TabsTrigger value="farmers">Farmers</TabsTrigger>
          <TabsTrigger value="products">Products</TabsTrigger>
          <TabsTrigger value="markets">Markets</TabsTrigger>
        </TabsList>

        <TabsContent value="farmers">
          <FavoriteList kind="farmers" render={(farmer) => <FarmerCard key={farmer.id} farmer={farmer} />} />
        </TabsContent>
        <TabsContent value="products">
          <FavoriteList kind="products" render={(product) => <ProductCard key={product.id} product={product} />} />
        </TabsContent>
        <TabsContent value="markets">
          <FavoriteList kind="markets" render={(market) => <MarketCard key={market.id} market={market} />} />
        </TabsContent>
      </Tabs>
    </section>
  );
}
