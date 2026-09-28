import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';
import { notify } from '../../../lib/toast';

export const PRODUCTS_PAGE_SIZE = 20;

const toPage = (data) => ({
  products: data.results,
  total: data.count,
  page: data.page,
  pageSize: data.page_size,
  totalPages: data.total_pages,
});


export function availabilityOf({ is_available: isAvailable, stock_quantity: stock }) {
  if (!isAvailable) return 'UNAVAILABLE';
  return stock > 0 ? 'IN_STOCK' : 'OUT_OF_STOCK';
}


export function useFarmerProductList(filters) {
  return useQuery({
    queryKey: farmerKeys.products.list(filters),
    queryFn: ({ signal }) =>
      farmerApi.getProducts({ ...filters, page: filters.page ?? 1, page_size: PRODUCTS_PAGE_SIZE }, { signal }),
    select: toPage,
    placeholderData: keepPreviousData,
    staleTime: STALE.SEARCH,
  });
}


export function useFarmerProductCounts(filters) {
  return useQuery({
    queryKey: [...farmerKeys.products.all(), 'counts', filters],
    queryFn: ({ signal }) => farmerApi.getProductCounts(filters, { signal }),
    placeholderData: keepPreviousData,
    staleTime: STALE.SEARCH,
  });
}

export function useBulkProducts() {
  const invalidate = useInvalidateProducts();
  return useMutation({
    mutationFn: farmerApi.bulkProducts,
    onSuccess: ({ updated }) => notify.success(`${updated} product${updated === 1 ? '' : 's'} updated`),
    onSettled: invalidate,
  });
}

export function useFarmerProduct(id, { enabled = true } = {}) {
  const productId = Number(id);
  return useQuery({
    queryKey: farmerKeys.products.detail(productId),
    queryFn: ({ signal }) => farmerApi.getProduct(productId, { signal }),
    staleTime: STALE.LIVE,
    refetchOnWindowFocus: false,
    enabled: enabled && Number.isInteger(productId) && productId > 0,
  });
}

export function useWeeklyTemplatePreview() {
  return useQuery({
    queryKey: farmerKeys.products.weeklyTemplate(),
    queryFn: ({ signal }) => farmerApi.getWeeklyTemplatePreview({ signal }),
    
    staleTime: STALE.LIVE,
  });
}




function mapListProducts(data, mapProduct) {
  if (!Array.isArray(data?.results)) return data;
  return { ...data, results: data.results.flatMap(mapProduct) };
}

async function snapshotProducts(queryClient) {
  const filters = { queryKey: farmerKeys.products.all() };
  await queryClient.cancelQueries(filters);
  return queryClient.getQueriesData(filters);
}

function restore(queryClient, snapshot) {
  snapshot?.forEach(([key, data]) => queryClient.setQueryData(key, data));
}

function patchProduct(queryClient, id, patch) {
  const apply = (product) => {
    const next = { ...product, ...patch(product) };
    return { ...next, availability: availabilityOf(next) };
  };
  queryClient.setQueriesData({ queryKey: farmerKeys.products.lists() }, (data) =>
    mapListProducts(data, (product) => [product.id === id ? apply(product) : product]),
  );
  queryClient.setQueryData(farmerKeys.products.detail(id), (product) => (product ? apply(product) : product));
}

function useInvalidateProducts() {
  const queryClient = useQueryClient();
  
  return () => {
    void queryClient.invalidateQueries({ queryKey: farmerKeys.products.all() });
    void queryClient.invalidateQueries({ queryKey: farmerKeys.dashboard.all() });
  };
}

function notifyRestock(count) {
  if (count > 0) {
    notify.info(`${count} shopper${count === 1 ? '' : 's'} told it's back in stock`);
  }
}




export function useSaveFarmerProduct(productId) {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateProducts();
  const isEdit = productId !== undefined;

  return useMutation({
    mutationFn: (payload) => (isEdit ? farmerApi.updateProduct(productId, payload) : farmerApi.createProduct(payload)),
    onSuccess: (product) => {
      queryClient.setQueryData(farmerKeys.products.detail(product.id), product);
      if (!isEdit) {
        notify.success('Produce submitted for review', {
          description: 'It is checked automatically; most listings go on sale within minutes.',
        });
      } else if (product.sent_for_review) {
        notify.success('Changes saved and sent for review', {
          description: 'It is hidden from shoppers until an administrator approves the changes. Open orders are not affected.',
        });
      } else {
        notify.success('Changes saved');
      }
      notifyRestock(product.restock_notified ?? 0);
    },
    onSettled: invalidate,
  });
}


export function useUpdateProductStock() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateProducts();

  return useMutation({
    mutationFn: ({ id, stockQuantity }) => farmerApi.updateProduct(id, { stock_quantity: stockQuantity }),
    onMutate: async ({ id, stockQuantity }) => {
      const snapshot = await snapshotProducts(queryClient);
      patchProduct(queryClient, id, () => ({ stock_quantity: stockQuantity }));
      return { snapshot };
    },
    onError: (_error, _variables, context) => restore(queryClient, context?.snapshot),
    onSuccess: (product) => notifyRestock(product.restock_notified ?? 0),
    onSettled: invalidate,
  });
}

export function useMarkProductSoldOut() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateProducts();

  return useMutation({
    mutationFn: (id) => farmerApi.markProductSoldOut(id),
    onMutate: async (id) => {
      const snapshot = await snapshotProducts(queryClient);
      patchProduct(queryClient, id, () => ({ stock_quantity: 0 }));
      return { snapshot };
    },
    onError: (_error, _id, context) => restore(queryClient, context?.snapshot),
    onSuccess: () => notify.success('Marked as sold out'),
    onSettled: invalidate,
  });
}

export function useArchiveProduct() {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateProducts();

  return useMutation({
    mutationFn: (id) => farmerApi.archiveProduct(id),
    onMutate: async (id) => {
      const snapshot = await snapshotProducts(queryClient);
      
      queryClient
        .getQueriesData({ queryKey: farmerKeys.products.lists() })
        .forEach(([key]) => {
          if (key[key.length - 1]?.state === 'archived') return;
          queryClient.setQueryData(key, (data) =>
            mapListProducts(data, (product) => (product.id === id ? [] : [product])),
          );
        });
      return { snapshot };
    },
    onError: (_error, _id, context) => restore(queryClient, context?.snapshot),
    onSuccess: () => notify.success('Product archived'),
    onSettled: invalidate,
  });
}

export function useApplyWeeklyTemplate() {
  const invalidate = useInvalidateProducts();
  return useMutation({
    mutationFn: farmerApi.applyWeeklyTemplate,
    onSuccess: ({ updated_count: updated, restock_notified: restocked }) => {
      notify.success(`Stock updated for ${updated} product${updated === 1 ? '' : 's'}`);
      notifyRestock(restocked ?? 0);
    },
    onSettled: invalidate,
  });
}


export function useProductPrecheck(params) {
  return useQuery({
    queryKey: farmerKeys.products.precheck(params),
    queryFn: ({ signal }) => farmerApi.precheckProduct(params, { signal }),
    enabled: Boolean(params),
    staleTime: STALE.MINUTE,
    placeholderData: keepPreviousData,
    meta: { silent: true },
  });
}
