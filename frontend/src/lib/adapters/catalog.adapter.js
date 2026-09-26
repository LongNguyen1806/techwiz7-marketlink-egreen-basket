import { adaptPaginated } from './pagination.adapter';
function isRecord(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
function readNumber(value) {
    if (typeof value === 'number' && Number.isFinite(value))
        return value;
    if (typeof value === 'string' && value.trim() !== '') {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
}
function readId(value) {
    if (typeof value === 'number')
        return value;
    if (isRecord(value))
        return readNumber(value.id);
    return null;
}
function isUnit(value) {
    return value === 'KG' || value === 'BUNCH' || value === 'PIECE' || value === 'PACK';
}
function isAvailability(value) {
    return value === 'IN_STOCK' || value === 'OUT_OF_STOCK' || value === 'UNAVAILABLE';
}
function isDay(value) {
    return (value === 1 ||
        value === 2 ||
        value === 3 ||
        value === 4 ||
        value === 5 ||
        value === 6 ||
        value === 7);
}
function readDays(value) {
    if (!Array.isArray(value))
        return [];
    return value.filter(isDay);
}
function availabilityOf(raw, stock) {
    if (isAvailability(raw.availability))
        return raw.availability;
    if (raw.is_available === false ||
        raw.is_archived === true ||
        raw.is_hidden_by_admin === true) {
        return 'UNAVAILABLE';
    }
    if (stock <= 0)
        return 'OUT_OF_STOCK';
    return 'IN_STOCK';
}
/** DRF ModelSerializer returns category/farmer as PK. UI reads nested name fields. */
export function adaptProduct(raw) {
    if (!isRecord(raw) || typeof raw.id !== 'number' || typeof raw.name !== 'string') {
        return null;
    }
    const categoryId = readId(raw.category);
    if (categoryId === null)
        return null;
    const categoryName = isRecord(raw.category) && typeof raw.category.name === 'string'
        ? raw.category.name
        : null;
    if (categoryName === null)
        return null;
    const farmerId = readId(raw.farmer);
    if (farmerId === null)
        return null;
    const stallName = isRecord(raw.farmer) && typeof raw.farmer.stall_name === 'string'
        ? raw.farmer.stall_name
        : null;
    if (stallName === null)
        return null;
    if (raw.price === undefined || raw.price === null)
        return null;
    if (!isUnit(raw.unit))
        return null;
    const stock = readNumber(raw.stock_quantity);
    if (stock === null)
        return null;
    return {
        id: raw.id,
        name: raw.name,
        image: typeof raw.image === 'string' ? raw.image : null,
        price: String(raw.price),
        unit: raw.unit,
        stock_quantity: stock,
        is_available: raw.is_available !== false,
        availability: availabilityOf(raw, stock),
        category: { id: categoryId, name: categoryName },
        farmer: { id: farmerId, stall_name: stallName },
        rating_avg: readNumber(raw.rating_avg),
        rating_count: readNumber(raw.rating_count) ?? 0,
        is_favorite: typeof raw.is_favorite === 'boolean' ? raw.is_favorite : null,
    };
}
export function adaptProductDetail(raw) {
    const card = adaptProduct(raw);
    if (!card || !isRecord(raw))
        return null;
    return {
        ...card,
        description: typeof raw.description === 'string' ? raw.description : null,
        markets: [],
    };
}
export function adaptFarmerProduct(raw) {
    const detail = adaptProductDetail(raw);
    if (!detail || !isRecord(raw))
        return null;
    return {
        ...detail,
        weekly_default_quantity: readNumber(raw.weekly_default_quantity),
        held_quantity: readNumber(raw.held_quantity) ?? 0,
        is_archived: raw.is_archived === true,
        is_hidden_by_admin: raw.is_hidden_by_admin === true,
        hidden_reason: typeof raw.hidden_reason === 'string' ? raw.hidden_reason : null,
        created_at: typeof raw.created_at === 'string' ? raw.created_at : '',
        updated_at: typeof raw.updated_at === 'string' ? raw.updated_at : '',
    };
}
export function adaptProductPage(raw) {
    const page = adaptPaginated(raw);
    return {
        ...page,
        results: page.results.flatMap((item) => {
            const product = adaptProduct(item);
            return product ? [product] : [];
        }),
    };
}
export function adaptFarmerProductPage(raw) {
    const page = adaptPaginated(raw);
    return {
        ...page,
        results: page.results.flatMap((item) => {
            const product = adaptFarmerProduct(item);
            return product ? [product] : [];
        }),
    };
}
export function adaptMarket(raw) {
    if (!isRecord(raw) || typeof raw.id !== 'number' || typeof raw.name !== 'string') {
        return null;
    }
    if (typeof raw.address !== 'string' || raw.address.trim() === '')
        return null;
    const latitude = readNumber(raw.latitude);
    const longitude = readNumber(raw.longitude);
    if (latitude === null || longitude === null)
        return null;
    if (typeof raw.open_time !== 'string' || typeof raw.close_time !== 'string') {
        return null;
    }
    return {
        id: raw.id,
        name: raw.name,
        address: raw.address,
        image: typeof raw.image === 'string' ? raw.image : null,
        latitude,
        longitude,
        operating_days: readDays(raw.operating_days),
        open_time: raw.open_time,
        close_time: raw.close_time,
        upcoming_closures: [],
        farmer_count: readNumber(raw.farmer_count) ?? 0,
        distance_km: readNumber(raw.distance_km),
        is_favorite: typeof raw.is_favorite === 'boolean' ? raw.is_favorite : null,
    };
}
export function adaptMarketDetail(raw) {
    const summary = adaptMarket(raw);
    if (!summary || !isRecord(raw))
        return null;
    return {
        ...summary,
        description: typeof raw.description === 'string' ? raw.description : null,
        map_provider: typeof raw.map_provider === 'string' ? raw.map_provider : 'OSM',
    };
}
export function adaptMarketPage(raw) {
    const page = adaptPaginated(raw);
    return {
        ...page,
        results: page.results.flatMap((item) => {
            const market = adaptMarket(item);
            return market ? [market] : [];
        }),
    };
}
export function adaptFarmerSummary(raw) {
    if (!isRecord(raw) || typeof raw.id !== 'number')
        return null;
    if (typeof raw.stall_name !== 'string' || raw.stall_name.trim() === '') {
        return null;
    }
    return {
        id: raw.id,
        stall_name: raw.stall_name,
        image: typeof raw.image === 'string' ? raw.image : null,
        rating_avg: readNumber(raw.rating_avg),
        rating_count: readNumber(raw.rating_count) ?? 0,
        markets: [],
        operating_days: readDays(raw.operating_days),
        in_stock_product_count: readNumber(raw.in_stock_product_count) ?? 0,
        upcoming_closures: [],
        distance_km: readNumber(raw.distance_km),
        is_favorite: typeof raw.is_favorite === 'boolean' ? raw.is_favorite : null,
    };
}
export function adaptFarmerPage(raw) {
    const page = adaptPaginated(raw);
    return {
        ...page,
        results: page.results.flatMap((item) => {
            const farmer = adaptFarmerSummary(item);
            return farmer ? [farmer] : [];
        }),
    };
}
