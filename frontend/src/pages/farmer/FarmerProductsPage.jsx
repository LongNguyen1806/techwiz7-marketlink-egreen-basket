import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useArchiveProduct, useFarmerMyProducts, useMarkSoldOut, useUpdateFarmerStock } from '../../features/farmer/hooks/useFarmerProducts';
import { EmptyState } from '../../components/feedback/EmptyState';
import { PageHeader } from '../../components/common/PageHeader';
import { PageSkeleton } from '../../components/feedback/PageSkeleton';
import { QuantityStepper } from '../../components/common/QuantityStepper';
import { LazyImage } from '../../components/common/LazyImage';
import { PriceTag } from '../../components/common/PriceTag';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import '../../styles/farmer/FarmerProductsPage.css';
const STATE_OPTIONS = [
    { value: '', label: 'All statuses' },
    { value: 'in_stock', label: 'In stock' },
    { value: 'out_of_stock', label: 'Out of stock' },
    { value: 'unavailable', label: 'Unavailable' },
    { value: 'hidden', label: 'Hidden' },
    { value: 'archived', label: 'Archived' },
];
const AVAILABILITY_LABEL = {
    IN_STOCK: 'In stock',
    OUT_OF_STOCK: 'Out of stock',
    UNAVAILABLE: 'Unavailable',
};
export default function FarmerProductsPage() {
    const [q, setQ] = useState('');
    const [state, setState] = useState('');
    const query = useFarmerMyProducts({
        q: q || undefined,
        state: state || undefined,
    });
    const stockMutation = useUpdateFarmerStock();
    const outMutation = useMarkSoldOut();
    const archiveMutation = useArchiveProduct();
    return (<div className="farmer-products-page">
      <PageHeader title="Your produce" description="Keep stock fresh, update prices, and mark sold-out items." actions={<Button asChild data-write>
            <Link to="/farmer/products/new">Add produce</Link>
          </Button>}/>

      <div className="page-primitive__actions-row">
        <Input label="Search products" value={q} onChange={(e) => setQ(e.target.value)} className="page-primitive__input-narrow"/>
        <select className="page-primitive__select" value={state} onChange={(e) => {
            const v = e.target.value;
            if (v === '' ||
                v === 'in_stock' ||
                v === 'out_of_stock' ||
                v === 'unavailable' ||
                v === 'hidden' ||
                v === 'archived') {
                setState(v);
            }
        }}>
          {STATE_OPTIONS.map((s) => (<option key={s.value || 'all'} value={s.value}>
              {s.label}
            </option>))}
        </select>
      </div>

      {query.isLoading ? (<PageSkeleton />) : query.isError ? (<EmptyState title="Products couldn't be loaded" actionLabel="Try again" onAction={() => query.refetch()}/>) : !query.data?.results.length ? (<EmptyState title="No produce listed yet" description="Add your first item so shoppers can pre-order from your stall."/>) : (<div className="page-primitive__table-wrap">
          <table className="page-primitive__table page-primitive__table-min-720">
            <thead className="page-primitive__table-head">
              <tr>
                <th className="page-primitive__table-th">Product</th>
                <th className="page-primitive__table-th">Price</th>
                <th className="page-primitive__table-th">Stock</th>
                <th className="page-primitive__table-th">Status</th>
                <th className="page-primitive__table-th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {query.data.results.map((p) => (<tr key={p.id} className="page-primitive__table-row">
                  <td className="page-primitive__table-td">
                    <div className="page-primitive__row-inner">
                      {p.image ? (<LazyImage src={p.image} alt="" className="page-primitive__thumb-sm"/>) : (<div className="page-primitive__thumb-fallback"/>)}
                      <div>
                        <Link to={`/farmer/products/${p.id}/edit`} className="page-primitive__font-medium page-primitive__link-underline">
                          {p.name}
                        </Link>
                        <p className="page-primitive__muted-xs">{p.category.name}</p>
                      </div>
                    </div>
                  </td>
                  <td className="page-primitive__table-td">
                    <PriceTag amount={p.price} unit={p.unit}/>
                  </td>
                  <td className="page-primitive__table-td">
                    <QuantityStepper value={p.stock_quantity} min={0} onChange={(value) => stockMutation.mutate({
                    id: p.id,
                    stock_quantity: value,
                })}/>
                  </td>
                  <td className="page-primitive__table-td">
                    <Badge variant={p.availability === 'IN_STOCK' ? 'success' : 'secondary'}>
                      {AVAILABILITY_LABEL[p.availability]}
                    </Badge>
                  </td>
                  <td className="page-primitive__table-td">
                    <div className="page-primitive__actions-row">
                      <Button asChild size="sm" variant="outline">
                        <Link to={`/farmer/products/${p.id}/edit`}>Edit</Link>
                      </Button>
                      <Button size="sm" variant="outline" data-write loading={outMutation.isPending} onClick={() => outMutation.mutate(p.id)}>
                        Mark sold out
                      </Button>
                      <Button size="sm" variant="destructive" data-write loading={archiveMutation.isPending} onClick={() => archiveMutation.mutate(p.id)}>
                        Archive
                      </Button>
                    </div>
                  </td>
                </tr>))}
            </tbody>
          </table>
        </div>)}
    </div>);
}

