import { useState } from 'react';
import { Link } from 'react-router-dom';

import {
  useAdminFarmers,
  useApproveFarmer,
  useRejectFarmer,
} from '../../hooks/queries/admin/useAdminFarmers';
import { useAdminMarkets } from '../../hooks/queries/admin/useAdminMarkets';
import { useAdminCategories } from '../../hooks/queries/admin/useAdminCategories';
import { useModerationProducts } from '../../hooks/queries/admin/useAdminModeration';
import {
  useApproveProduct,
  useApproveProducts,
  useRejectProduct,
} from '../../hooks/queries/admin/useAdminApprovals';
import { ConfirmDialog } from '@/components/common/modal/ConfirmDialog';
import { EmptyState } from '@/components/common/feedback/EmptyState';
import { PageHeader } from '@/components/common/layout/PageHeader';
import { PageSkeleton } from '@/components/common/feedback/PageSkeleton';
import { LazyImage } from '@/components/common/cards/LazyImage';
import { Card, CardContent, CardHeader } from '@/components/common/cards/Card';
import { Badge } from '@/components/common/badges/Badge';
import { Button } from '@/components/common/forms/Button';
import { Textarea } from '@/components/common/forms/Textarea';
import { FilterBar } from '@/components/common/table/FilterBar';
import { SortSelect } from '@/components/common/table/SortSelect';
import { SortableTh } from '@/components/common/table/SortableTh';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/common/layout/Tabs';
import { formatDate, formatDateTime, formatVnd } from '@/utils/formatters';

import './AdminApprovalsPage.css';

const REASON_MIN_LENGTH = 5;

const PRODUCT_SORT = [
  { value: 'oldest', label: 'Waiting longest' },
  { value: 'newest', label: 'Newest first' },
  { value: 'stall_name', label: 'Stall A–Z' },
  { value: 'name', label: 'Name A–Z' },
  { value: '-price', label: 'Highest price' },
];

/** A queue is worked from the front, so both tabs open on whatever has waited longest. */
export default function AdminApprovalsPage() {
  const [stallFilters, setStallFilters] = useState({});
  const [stallOrdering, setStallOrdering] = useState('date_joined');
  const [productFilters, setProductFilters] = useState({});
  const [productOrdering, setProductOrdering] = useState('oldest');
  const [rejecting, setRejecting] = useState(null);
  const [reason, setReason] = useState('');

  const marketsQuery = useAdminMarkets();
  const categoriesQuery = useAdminCategories();

  const stallsQuery = useAdminFarmers({
    ...stallFilters,
    status: 'PENDING',
    ordering: stallOrdering,
  });
  const productsQuery = useModerationProducts({
    ...productFilters,
    review_status: 'PENDING',
    ordering: productOrdering,
  });

  const approveStall = useApproveFarmer();
  const rejectStall = useRejectFarmer();
  const approveProduct = useApproveProduct();
  const approveProducts = useApproveProducts();
  const rejectProduct = useRejectProduct();

  const stallCount = stallsQuery.data?.count ?? 0;
  const productCount = productsQuery.data?.count ?? 0;

  const stallFilterFields = [
    { name: 'q', label: 'Search stall, email or phone', type: 'search' },
    {
      name: 'market_id',
      label: 'Market',
      type: 'select',
      allLabel: 'Any market',
      options: (marketsQuery.data?.results ?? []).map((m) => ({
        value: String(m.id),
        label: m.name,
      })),
    },
  ];

  const productFilterFields = [
    { name: 'q', label: 'Search product or stall', type: 'search' },
    {
      name: 'category_id',
      label: 'Category',
      type: 'select',
      allLabel: 'Any category',
      options: (categoriesQuery.data ?? []).map((c) => ({
        value: String(c.id),
        label: c.name,
      })),
    },
  ];

  // Grouped by stall, because a stall that has just signed up usually adds several listings
  // at once and they are judged together: the same photographer, the same wording, the same
  // idea of what a description is for.
  const byStall = [];
  const seen = new Map();
  for (const product of productsQuery.data?.results ?? []) {
    const id = product.farmer.id;
    if (!seen.has(id)) {
      seen.set(id, { farmer: product.farmer, products: [] });
      byStall.push(seen.get(id));
    }
    seen.get(id).products.push(product);
  }

  // One dialog for both kinds. Refusing is the same act either way: say why, in words the
  // person on the other end can act on.
  const openReject = (kind, item) => {
    setRejecting({ kind, id: item.id, name: item.stall_name ?? item.name });
    setReason('');
  };

  const confirmReject = () => {
    if (!rejecting) return;
    const mutation = rejecting.kind === 'stall' ? rejectStall : rejectProduct;
    mutation.mutate({ id: rejecting.id, reason }, { onSuccess: () => setRejecting(null) });
  };

  const sortStalls = (next) => setStallOrdering(next);

  return (
    <div className="page-primitive__stack-4">
      <PageHeader
        title="Waiting for approval"
        description="New stalls and new listings, before shoppers see them. Approving takes one click; refusing asks for a reason the applicant can act on."
      />

      <Tabs defaultValue={stallCount === 0 && productCount > 0 ? 'products' : 'stalls'}>
        <TabsList>
          {/* The counts are on the tabs because the point of this screen is how much is left. */}
          <TabsTrigger value="stalls">Stalls ({stallCount})</TabsTrigger>
          <TabsTrigger value="products">Products ({productCount})</TabsTrigger>
        </TabsList>

        <TabsContent value="stalls">
          <FilterBar
            fields={stallFilterFields}
            value={stallFilters}
            onChange={setStallFilters}
            onReset={() => setStallFilters({})}
          />

          {stallsQuery.isLoading ? (
            <PageSkeleton />
          ) : !stallsQuery.data?.results.length ? (
            <EmptyState
              title="No stalls waiting"
              description="Applications appear here as growers sign up."
            />
          ) : (
            <div className="page-primitive__table-wrap">
              <table className="page-primitive__table page-primitive__table-min-800">
                <thead className="page-primitive__table-head">
                  <tr>
                    <SortableTh
                      column="stall_name"
                      current={stallOrdering}
                      onSort={sortStalls}
                    >
                      Stall
                    </SortableTh>
                    <SortableTh column="email" current={stallOrdering} onSort={sortStalls}>
                      Contact
                    </SortableTh>
                    <SortableTh
                      column="date_joined"
                      current={stallOrdering}
                      onSort={sortStalls}
                    >
                      Applied
                    </SortableTh>
                    <SortableTh
                      column="product_count"
                      current={stallOrdering}
                      onSort={sortStalls}
                    >
                      Listings
                    </SortableTh>
                    <th className="page-primitive__table-th">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {stallsQuery.data.results.map((stall) => (
                    <tr key={stall.id} className="page-primitive__table-row">
                      <td className="page-primitive__table-td">
                        <Link
                          className="admin-approvals-page__name"
                          to={`/admin/farmers/${stall.id}`}
                        >
                          {stall.stall_name}
                        </Link>
                        <span className="page-primitive__muted-xs admin-approvals-page__table-td-stacked">
                          {stall.contact_person}
                        </span>
                      </td>
                      <td className="page-primitive__table-td">
                        {stall.email}
                        <span className="page-primitive__muted-xs admin-approvals-page__table-td-stacked">
                          {stall.phone}
                        </span>
                      </td>
                      <td className="page-primitive__table-td">
                        {formatDate(stall.date_joined)}
                      </td>
                      <td className="page-primitive__table-td">{stall.product_count}</td>
                      <td className="page-primitive__table-td">
                        <div className="page-primitive__actions-row">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openReject('stall', stall)}
                          >
                            Refuse
                          </Button>
                          <Button
                            size="sm"
                            loading={approveStall.isPending}
                            onClick={() => approveStall.mutate(stall.id)}
                          >
                            Approve
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="products">
          <FilterBar
            fields={productFilterFields}
            value={productFilters}
            onChange={setProductFilters}
            onReset={() => setProductFilters({})}
          />
          <SortSelect
            id="approvals-product-sort"
            options={PRODUCT_SORT}
            value={productOrdering}
            onChange={setProductOrdering}
          />

          {productsQuery.isLoading ? (
            <PageSkeleton />
          ) : !byStall.length ? (
            <EmptyState
              title="No listings waiting"
              description="A new listing, or one whose name, photo, description or category changed, appears here."
            />
          ) : (
            <div className="admin-approvals-page__stalls">
              {byStall.map(({ farmer, products }) => (
                <Card key={farmer.id}>
                  <CardHeader className="admin-approvals-page__stall-head">
                    <div className="admin-approvals-page__stall-title">
                      <Link
                        className="admin-approvals-page__name"
                        to={`/admin/farmers/${farmer.id}`}
                      >
                        {farmer.stall_name}
                      </Link>
                      <Badge variant="warning">{products.length} waiting</Badge>
                    </div>
                    {/* Whole-stall approval, for the common case: several listings written
                        the same day by the same person, judged in one read. It sits in the
                        header, away from the per-listing buttons, so it is never the
                        Approve that happens to be nearest the thumb. */}
                    <Button
                      size="sm"
                      loading={approveProducts.isPending}
                      onClick={() =>
                        approveProducts.mutate(products.map((item) => item.id))
                      }
                    >
                      Approve all {products.length}
                    </Button>
                  </CardHeader>

                  <CardContent className="admin-approvals-page__items">
                    {products.map((p) => (
                      <div key={p.id} className="admin-approvals-page__item">
                        <div className="admin-approvals-page__info">
                          <LazyImage
                            src={p.image}
                            alt=""
                            className="admin-approvals-page__thumb"
                          />
                          <div className="admin-approvals-page__text">
                            <p className="admin-approvals-page__item-name">{p.name}</p>
                            <p className="page-primitive__muted-xs">
                              {formatVnd(p.price)} / {p.unit} · {p.category?.name} ·{' '}
                              {p.stock_quantity} in stock · added{' '}
                              {formatDateTime(p.created_at)}
                            </p>
                            {/* Most refusals come from the description, so it is on the row
                                rather than a click away. */}
                            {p.description ? (
                              <p className="admin-approvals-page__description">
                                {p.description}
                              </p>
                            ) : null}
                          </div>
                        </div>
                        <div className="page-primitive__actions-row">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openReject('product', p)}
                          >
                            Refuse
                          </Button>
                          <Button
                            size="sm"
                            loading={approveProduct.isPending}
                            onClick={() => approveProduct.mutate(p.id)}
                          >
                            Approve
                          </Button>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={Boolean(rejecting)}
        onOpenChange={(open) => {
          if (!open) setRejecting(null);
        }}
        title={`Refuse ${rejecting?.name ?? 'this'}?`}
        description={
          rejecting?.kind === 'stall'
            ? 'The grower is told, and can apply again once the problem is fixed.'
            : 'The stall is told and the listing stays off sale. It comes back here once they have changed it.'
        }
        confirmLabel="Refuse"
        destructive
        loading={rejectStall.isPending || rejectProduct.isPending}
        confirmDisabled={reason.trim().length < REASON_MIN_LENGTH}
        onConfirm={confirmReject}
      >
        <Textarea
          className="admin-approvals-page__reason"
          placeholder="What needs to change?"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </ConfirmDialog>
    </div>
  );
}
