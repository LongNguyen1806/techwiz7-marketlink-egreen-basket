function pageFromUrl(url) {
  if (!url) return null;
  try {
    const parsed = new URL(url, 'http://localhost');
    const page = parsed.searchParams.get('page');
    if (!page) return null;
    const n = Number(page);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

export function adaptPaginated(raw, fallbackPageSize = 20) {
  if (!raw) {
    return {
      count: 0,
      page: 1,
      page_size: fallbackPageSize,
      total_pages: 0,
      next: null,
      previous: null,
      results: [],
    };
  }

  if (Array.isArray(raw)) {
    return {
      count: raw.length,
      page: 1,
      page_size: raw.length || fallbackPageSize,
      total_pages: raw.length > 0 ? 1 : 0,
      next: null,
      previous: null,
      results: raw,
    };
  }

  if (typeof raw !== 'object') {
    return {
      count: 0,
      page: 1,
      page_size: fallbackPageSize,
      total_pages: 0,
      next: null,
      previous: null,
      results: [],
    };
  }

  if (
    typeof raw.page === 'number' &&
    typeof raw.page_size === 'number' &&
    typeof raw.total_pages === 'number' &&
    Array.isArray(raw.results)
  ) {
    return {
      count: typeof raw.count === 'number' ? raw.count : raw.results.length,
      page: raw.page,
      page_size: raw.page_size,
      total_pages: raw.total_pages,
      next: typeof raw.next === 'number' || raw.next === null ? raw.next : null,
      previous:
        typeof raw.previous === 'number' || raw.previous === null ? raw.previous : null,
      results: raw.results,
    };
  }

  const results = Array.isArray(raw.results) ? raw.results : [];
  const count = typeof raw.count === 'number' ? raw.count : results.length;
  const pageSize =
    results.length > 0 && count > results.length
      ? results.length
      : results.length || fallbackPageSize;
  const totalPages = pageSize > 0 ? Math.max(1, Math.ceil(count / pageSize)) : 0;
  const nextPage = pageFromUrl(raw.next);
  const prevPage = pageFromUrl(raw.previous);
  const currentPage =
    prevPage !== null ? prevPage + 1 : nextPage !== null ? nextPage - 1 : 1;

  return {
    count,
    page: currentPage,
    page_size: pageSize,
    total_pages: totalPages,
    next: nextPage,
    previous: prevPage,
    results,
  };
}

export function emptyPage(pageSize = 20) {
  return adaptPaginated(undefined, pageSize);
}
