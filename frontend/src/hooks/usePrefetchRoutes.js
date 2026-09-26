
export function usePrefetchRoutes() {
  const noop = () => {};
  return {
    prefetchMarkets: noop,
    prefetchProducts: noop,
    prefetchFarmers: noop,
  };
}
