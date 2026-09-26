import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { catalogApi } from '../../../api/guest/catalogApi';
import { publicKeys } from '../../../constants/queryKeys';
import { STALE } from '../../../constants/staleTimes';

export function usePublicConfig() {
  return useQuery({
    queryKey: publicKeys.config(),
    queryFn: ({ signal }) => catalogApi.getConfig({ signal }),
    staleTime: STALE.STATIC,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: publicKeys.categories(),
    queryFn: ({ signal }) => catalogApi.getCategories({ signal }),
    staleTime: STALE.STATIC,
  });
}

export function usePublicMarkets(params = {}) {
  return useQuery({
    queryKey: publicKeys.markets(params),
    queryFn: ({ signal }) => catalogApi.getMarkets(params, { signal }),
    staleTime: STALE.LONG,
    placeholderData: keepPreviousData,
  });
}


export function usePublicProducts(params = {}) {
  return useQuery({
    queryKey: publicKeys.products(params),
    queryFn: ({ signal }) => catalogApi.getProducts(params, { signal }),
    staleTime: STALE.MEDIUM,
    placeholderData: keepPreviousData,
  });
}

const flattenProductPages = (data) => ({
  products: data.pages.flatMap((page) => page.results),
  total: data.pages[0]?.count ?? 0,
});


export function usePublicProductList(filters) {
  return useInfiniteQuery({
    queryKey: publicKeys.productList(filters),
    queryFn: ({ pageParam, signal }) =>
      catalogApi.getProducts({ ...filters, page: pageParam, page_size: 20 }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    select: flattenProductPages,
    placeholderData: keepPreviousData,
    staleTime: STALE.SEARCH,
  });
}


export function usePublicProduct(id) {
  const productId = Number(id);
  return useQuery({
    queryKey: publicKeys.product(productId),
    queryFn: ({ signal }) => catalogApi.getProduct(productId, { signal }),
    staleTime: STALE.LIVE,
    enabled: Number.isInteger(productId) && productId > 0,
  });
}

const flattenReviewPages = (data) => ({
  reviews: data.pages.flatMap((page) => page.results),
  summary: data.pages[0]?.summary ?? null,
  total: data.pages[0]?.count ?? 0,
});

export function usePublicProductReviews(id) {
  const productId = Number(id);
  return useInfiniteQuery({
    queryKey: publicKeys.productReviews(productId),
    queryFn: ({ pageParam, signal }) => catalogApi.getProductReviews(productId, { page: pageParam }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    select: flattenReviewPages,
    staleTime: STALE.MEDIUM,
    enabled: Number.isInteger(productId) && productId > 0,
  });
}

export function usePublicFarmers(params = {}) {
  return useQuery({
    queryKey: publicKeys.farmers(params),
    queryFn: ({ signal }) => catalogApi.getFarmers(params, { signal }),
    staleTime: STALE.MEDIUM,
    placeholderData: keepPreviousData,
  });
}
