/**
 * Warms the public list routes on hover, so the first paint after the click has data already.
 *
 * The queries belong to the Guest scope (PU-03, PU-10, PU-06), which the Admin branch owns, so
 * this hook stays a no-op until that API layer lands. The header keeps calling it either way, and
 * wiring it up later is a change in one file.
 */
export function usePrefetchRoutes() {
  const noop = () => {};
  return {
    prefetchMarkets: noop,
    prefetchProducts: noop,
    prefetchFarmers: noop,
  };
}
