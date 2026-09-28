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

const flattenMarketPages = (data) => ({
  markets: data.pages.flatMap((page) => page.results),
  total: data.pages[0]?.count ?? 0,
});

export function usePublicMarketList(filters) {
  return useInfiniteQuery({
    queryKey: publicKeys.marketList(filters),
    queryFn: ({ pageParam, signal }) =>
      catalogApi.getMarkets({ ...filters, page: pageParam, page_size: 20 }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    select: flattenMarketPages,
    placeholderData: keepPreviousData,
    staleTime: STALE.SEARCH,
  });
}

export function usePublicMarket(id, coords = {}) {
  const marketId = Number(id);
  return useQuery({
    queryKey: publicKeys.market(marketId, coords),
    queryFn: ({ signal }) => catalogApi.getMarket(marketId, coords, { signal }),
    staleTime: STALE.MEDIUM,
    placeholderData: keepPreviousData,
    enabled: Number.isInteger(marketId) && marketId > 0,
  });
}

const flattenFarmerPages = (data) => ({
  farmers: data.pages.flatMap((page) => page.results),
  total: data.pages[0]?.count ?? 0,
});

export function usePublicMarketFarmers(id, { day } = {}) {
  const marketId = Number(id);
  return useInfiniteQuery({
    queryKey: publicKeys.marketFarmers(marketId, { day }),
    queryFn: ({ pageParam, signal }) =>
      catalogApi.getMarketFarmers(marketId, { day, page: pageParam, page_size: 20 }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    select: flattenFarmerPages,
    placeholderData: keepPreviousData,
    staleTime: STALE.MEDIUM,
    enabled: Number.isInteger(marketId) && marketId > 0,
  });
}

export function usePublicFarmerList(filters) {
  return useInfiniteQuery({
    queryKey: publicKeys.farmerList(filters),
    queryFn: ({ pageParam, signal }) =>
      catalogApi.getFarmers({ ...filters, page: pageParam, page_size: 20 }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    select: flattenFarmerPages,
    placeholderData: keepPreviousData,
    staleTime: STALE.SEARCH,
  });
}

export function usePublicFarmer(id, coords = {}) {
  const farmerId = Number(id);
  return useQuery({
    queryKey: publicKeys.farmer(farmerId, coords),
    queryFn: ({ signal }) => catalogApi.getFarmer(farmerId, coords, { signal }),
    staleTime: STALE.MEDIUM,
    placeholderData: keepPreviousData,
    enabled: Number.isInteger(farmerId) && farmerId > 0,
  });
}

export function usePublicFarmerReviews(id) {
  const farmerId = Number(id);
  return useInfiniteQuery({
    queryKey: publicKeys.farmerReviews(farmerId),
    queryFn: ({ pageParam, signal }) => catalogApi.getFarmerReviews(farmerId, { page: pageParam }, { signal }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => lastPage.next ?? undefined,
    select: flattenReviewPages,
    staleTime: STALE.MEDIUM,
    enabled: Number.isInteger(farmerId) && farmerId > 0,
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
