import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

import {
  useAdminFarmers,
  useApproveFarmer,
  useRejectFarmer,
} from '../../hooks/queries/admin/useAdminFarmers';
import { useAdminMarkets } from '../../hooks/queries/admin/useAdminMarkets';
import {
  useAdminMarketRequests,
  useApproveMarketRequest,
  useRejectMarketRequest,
} from '../../hooks/queries/admin/useAdminMarketRequests';
import { useAdminCategories } from '../../hooks/queries/admin/useAdminCategories';
import { useModerationProducts } from '../../hooks/queries/admin/useAdminModeration';
import {
  useApproveProduct,
  useApproveProducts,
  useRejectProduct,
} from '../../hooks/queries/admin/useAdminApprovals';
import { useAIRecheck } from '../../hooks/queries/admin/useAdminAIReview';
import { AIReviewPanel } from '@/components/admin/AIReviewPanel';
import { AIDecisionsPanel } from './AdminAIDecisionsPage';
import { useAIReviewStats } from '../../hooks/queries/admin/useAdminAIReview';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { PageSkeleton } from '@/components/feedback/PageSkeleton';
import { LazyImage } from '@/components/common/LazyImage';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { FilterBar } from '@/components/common/table/FilterBar';
import { SortSelect } from '@/components/common/SortSelect';
import { SortableTh } from '@/components/common/SortableTh';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/Tabs';
import { formatDate, formatDateTime, formatVnd } from '@/utils/formatters';

import './AdminApprovalsPage.css';

const REASON_MIN_LENGTH = 5;

const PRODUCT_SORT = [
  { value: 'oldest', label: 'Waiting longest' },
  { value: 'newest', label: 'Newest first' },
  { value: 'stall_name', label: 'Stall A–Z' },
  { value: 'name', label: 'Name A–Z' },
  { value: '-price', label: 'Highest price' },
  { value: '-ai_risk', label: 'Highest AI risk' },
];

const AI_FILTERS = [
  { value: '', label: 'All' },
  { value: 'LIKELY_VIOLATION', label: 'Likely violation' },
  { value: 'NEEDS_REVIEW', label: 'Worth a look' },
  { value: 'PASS', label: 'AI passed' },
  { value: 'UNAVAILABLE', label: 'AI unavailable' },
  { value: 'NONE', label: 'Not reviewed' },
];

function reasonFromFindings(findings) {
  const lines = findings.map((finding) => `- ${finding.message}`);
  return `Please fix the following before this listing can go on sale:\n${lines.join('\n')}`;
}

export default function AdminApprovalsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const linkedProduct = searchParams.get('product');
  const aiStats = useAIReviewStats(30);
  const aiUnchecked = aiStats.data?.unchecked_ai_decisions ?? 0;
  const [stallFilters, setStallFilters] = useState({});
  const [stallOrdering, setStallOrdering] = useState('date_joined');
  const [marketFilters, setMarketFilters] = useState({});
  const [marketOrdering, setMarketOrdering] = useState('requested_at');
  const [productFilters, setProductFilters] = useState(() => (linkedProduct ? { product_id: linkedProduct } : {}));
  const [confirmAIPassed, setConfirmAIPassed] = useState(false);
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

  const marketRequestsQuery = useAdminMarketRequests({
    ...marketFilters,
    ordering: marketOrdering,
  });

  const approveStall = useApproveFarmer();
  const rejectStall = useRejectFarmer();
  const approveMarket = useApproveMarketRequest();
  const rejectMarket = useRejectMarketRequest();
  const approveProduct = useApproveProduct();
  const approveProducts = useApproveProducts();
  const rejectProduct = useRejectProduct();
  const recheck = useAIRecheck();

  const stallCount = stallsQuery.data?.count ?? 0;
  const productCount = productsQuery.data?.count ?? 0;
  const marketCount = marketRequestsQuery.data?.count ?? 0;
  const aiPassed = (productsQuery.data?.results ?? []).filter((item) => item.ai_review?.verdict === 'PASS');
  const aiFilter = productFilters.ai_verdict ?? '';

  const showAllProducts = () => {
    setProductFilters({});
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.delete('product');
        return next;
      },
      { replace: true },
    );
  };

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

  const openReject = (kind, item) => {
    setRejecting({ kind, id: item.id, name: item.stall_name ?? item.name, findings: item.ai_review?.findings ?? [] });
    setReason('');
  };

  const confirmReject = () => {
    if (!rejecting) return;
    const mutations = { stall: rejectStall, product: rejectProduct, market: rejectMarket };
    mutations[rejecting.kind].mutate({ id: rejecting.id, reason }, { onSuccess: () => setRejecting(null) });
  };

  const openRejectMarket = (request) => {
    setRejecting({
      kind: 'market',
      id: request.id,
      name: `${request.stall_name} at ${request.market_name}`,
      findings: [],
    });
    setReason('');
  };

  const sortStalls = (next) => setStallOrdering(next);
  const sortMarketRequests = (next) => setMarketOrdering(next);

  const rejectDescriptions = {
    stall: 'The grower is told, and can apply again once the problem is fixed.',
    product: 'The stall is told and the listing stays off sale. It comes back here once they have changed it.',
    market: 'The stall is told why and can send a new request. Its other markets keep trading as before.',
  };

  let defaultTab = 'stalls';
  if (linkedProduct || (stallCount === 0 && productCount > 0)) defaultTab = 'products';
  else if (stallCount === 0 && productCount === 0 && marketCount > 0) defaultTab = 'markets';

  const requestedTab = searchParams.get('tab');
  const tab = ['stalls', 'products', 'markets', 'ai'].includes(requestedTab) ? requestedTab : defaultTab;

  return (
    <div className="page-primitive__stack-4">
      <PageHeader
        title="Waiting for approval"
        description="New stalls, new listings and stalls joining another market, before shoppers see them. The first three tabs are yours to decide; the AI tab is what the AI decided on its own, to look over."
      />

      <Tabs
        value={tab}
        onValueChange={(next) => {
          const params = new URLSearchParams(searchParams);
          params.set('tab', next);
          params.delete('product');
          setSearchParams(params, { replace: true });
        }}
      >
        <TabsList>
          <TabsTrigger value="stalls">Stalls ({stallCount})</TabsTrigger>
          <TabsTrigger value="products">Products ({productCount})</TabsTrigger>
          <TabsTrigger value="markets">Markets ({marketCount})</TabsTrigger>
          <TabsTrigger value="ai">
            <Sparkles className="admin-approvals-page__tab-icon" aria-hidden="true" />
            AI decisions ({aiUnchecked})
          </TabsTrigger>
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

          <div className="admin-approvals-page__ai-bar">
            <span className="admin-approvals-page__ai-label">
              <Sparkles aria-hidden className="admin-approvals-page__ai-icon" />
              AI review
            </span>
            <div className="admin-approvals-page__ai-filters" role="group" aria-label="Filter by AI review">
              {AI_FILTERS.map((option) => (
                <Button
                  key={option.value || 'all'}
                  size="sm"
                  variant={aiFilter === option.value ? 'default' : 'outline'}
                  aria-pressed={aiFilter === option.value}
                  onClick={() => setProductFilters((current) => ({ ...current, ai_verdict: option.value || undefined }))}
                >
                  {option.label}
                </Button>
              ))}
            </div>
            {aiPassed.length ? (
              <Button
                size="sm"
                variant="secondary"
                loading={approveProducts.isPending}
                onClick={() => setConfirmAIPassed(true)}
                className="admin-approvals-page__ai-approve"
              >
                Approve {aiPassed.length} AI-passed
              </Button>
            ) : null}
          </div>

          {linkedProduct && productFilters.product_id ? (
            <p className="page-primitive__warn-banner admin-approvals-page__linked">
              Showing the listing from an AI alert.{' '}
              <button type="button" className="page-primitive__link-underline" onClick={showAllProducts}>
                Show every listing waiting
              </button>
            </p>
          ) : null}

          {productsQuery.isLoading ? (
            <PageSkeleton />
          ) : !byStall.length ? (
            <EmptyState
              title="No listings waiting"
              description="A listing the AI could not settle appears here: unsure, held for a likely problem, or not checked because the AI was unavailable. Listings the AI passed go on sale at once and are listed in AI decisions."
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
                            {p.description ? (
                              <p className="admin-approvals-page__description">
                                {p.description}
                              </p>
                            ) : null}
                            <AIReviewPanel
                              review={p.ai_review}
                              photoCheck={p.ai_photo_check}
                              onRecheck={() => recheck.mutate(p.id)}
                              rechecking={recheck.isPending && recheck.variables === p.id}
                            />
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

        <TabsContent value="markets">
          <FilterBar
            fields={stallFilterFields}
            value={marketFilters}
            onChange={setMarketFilters}
            onReset={() => setMarketFilters({})}
          />

          {marketRequestsQuery.isLoading ? (
            <PageSkeleton />
          ) : !marketRequestsQuery.data?.results.length ? (
            <EmptyState
              title="No market requests waiting"
              description="A stall that asks to sell at another market appears here until you decide."
            />
          ) : (
            <div className="page-primitive__table-wrap">
              <table className="page-primitive__table page-primitive__table-min-800">
                <thead className="page-primitive__table-head">
                  <tr>
                    <SortableTh column="stall_name" current={marketOrdering} onSort={sortMarketRequests}>
                      Stall
                    </SortableTh>
                    <SortableTh column="market" current={marketOrdering} onSort={sortMarketRequests}>
                      Market
                    </SortableTh>
                    <th className="page-primitive__table-th">Stall number(s)</th>
                    <SortableTh column="requested_at" current={marketOrdering} onSort={sortMarketRequests}>
                      Requested
                    </SortableTh>
                    <th className="page-primitive__table-th">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {marketRequestsQuery.data.results.map((request) => (
                    <tr key={request.id} className="page-primitive__table-row">
                      <td className="page-primitive__table-td">
                        <Link className="admin-approvals-page__name" to={`/admin/farmers/${request.farmer_id}`}>
                          {request.stall_name}
                        </Link>
                        <span className="page-primitive__muted-xs admin-approvals-page__table-td-stacked">
                          {request.email} · {request.phone}
                        </span>
                        {request.farmer_status !== 'APPROVED' ? (
                          <Badge variant="warning">Stall not approved yet</Badge>
                        ) : null}
                      </td>
                      <td className="page-primitive__table-td">{request.market_name}</td>
                      <td className="page-primitive__table-td">{request.stall_label}</td>
                      <td className="page-primitive__table-td">{formatDate(request.requested_at)}</td>
                      <td className="page-primitive__table-td">
                        <div className="page-primitive__actions-row">
                          <Button size="sm" variant="outline" onClick={() => openRejectMarket(request)}>
                            Refuse
                          </Button>
                          <Button
                            size="sm"
                            loading={approveMarket.isPending && approveMarket.variables === request.id}
                            onClick={() => approveMarket.mutate(request.id)}
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

        <TabsContent value="ai">
          <AIDecisionsPanel />
        </TabsContent>
      </Tabs>

      <ConfirmDialog
        open={Boolean(rejecting)}
        onOpenChange={(open) => {
          if (!open) setRejecting(null);
        }}
        title={`Refuse ${rejecting?.name ?? 'this'}?`}
        description={rejectDescriptions[rejecting?.kind] ?? ''}
        confirmLabel="Refuse"
        destructive
        loading={rejectStall.isPending || rejectProduct.isPending || rejectMarket.isPending}
        confirmDisabled={reason.trim().length < REASON_MIN_LENGTH}
        onConfirm={confirmReject}
      >
        <Textarea
          className="admin-approvals-page__reason"
          placeholder="What needs to change?"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
        {rejecting?.kind === 'product' && rejecting.findings?.length ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="admin-approvals-page__ai-fill"
            onClick={() => setReason(reasonFromFindings(rejecting.findings))}
          >
            <Sparkles aria-hidden className="admin-approvals-page__ai-icon" />
            Start from the AI findings
          </Button>
        ) : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={confirmAIPassed}
        onOpenChange={setConfirmAIPassed}
        title={`Approve ${aiPassed.length} listing${aiPassed.length === 1 ? '' : 's'} the AI passed?`}
        description="Neither the rule checks nor the AI found a problem with these. Shoppers will see them as soon as you confirm; the stalls are told."
        confirmLabel={`Approve ${aiPassed.length}`}
        loading={approveProducts.isPending}
        onConfirm={() =>
          approveProducts.mutate(
            aiPassed.map((item) => item.id),
            { onSettled: () => setConfirmAIPassed(false) },
          )
        }
      >
        <ul className="admin-approvals-page__ai-list">
          {aiPassed.map((item) => (
            <li key={item.id}>
              {item.name} · {item.farmer.stall_name}
            </li>
          ))}
        </ul>
      </ConfirmDialog>
    </div>
  );
}
