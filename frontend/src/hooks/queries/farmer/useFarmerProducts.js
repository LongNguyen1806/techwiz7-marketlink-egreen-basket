import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { farmerApi } from '../../../api/farmer/farmerApi';
import { farmerKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';
import { notify } from '../../../lib/toast';

export const PRODUCTS_PAGE_SIZE = 20;

const flattenPages = (data) => ({
  products: data.pages.flatMap((page) => page.results),
  total: data.pages[0]?.count ?? 0,
});


export function availabilityOf({ is_available: isAvailable, stock_quantity: stock }) {
  if (!isAvailable) return 'UNAVAILABLE';
  return stock > 0 ? 'IN_STOCK' : 'OUT_OF_STOCK';
}


export function useFarmerProductList(filters) {
  return useInfiniteQuery({
    queryKey: farmerKeys.products.list(filters),
    queryFn: ({ pageParam, signal }) =>
      farmerApi.getProducts({ ...filters, page: pageParam, page_size: PRODUCTS_PAGE_SIZE }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    select: flattenPages,
    placeholderData: keepPreviousData,
    staleTime: STALE.SEARCH,
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
  if (!data?.pages) return data;
  return {
    ...data,
    pages: data.pages.map((page) => ({ ...page, results: page.results.flatMap(mapProduct) })),
  };
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
      notify.success(isEdit ? 'Changes saved' : 'Produce listed');
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
