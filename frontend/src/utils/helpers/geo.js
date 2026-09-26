/** Haversine distance in km between two WGS84 points. */
export function distanceKm(lat1, lng1, lat2, lng2) {
    const toRad = (d) => (d * Math.PI) / 180;
    const R = 6371;
    const dLat = toRad(lat2 - lat1);
    const dLng = toRad(lng2 - lng1);
    const a = Math.sin(dLat / 2) ** 2 +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
export function googleMapsDirectionsUrl(latitude, longitude) {
    return `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}`;
}
export function osmDirectionsUrl(latitude, longitude) {
    return `https://www.openstreetmap.org/directions?to=${latitude}%2C${longitude}`;
}
/** Labels for DayOfWeek (1=Mon … 7=Sun). */
export const DAY_OF_WEEK_LABELS = {
    1: 'Mon',
    2: 'Tue',
    3: 'Wed',
    4: 'Thu',
    5: 'Fri',
    6: 'Sat',
    7: 'Sun',
};
/** @deprecated Prefer DAY_OF_WEEK_LABELS */
export const WEEKDAY_LABELS = DAY_OF_WEEK_LABELS;
/** Convert JS Date.getDay() (0=Sun) to DayOfWeek (1=Mon…7=Sun). */
export function jsDayToDayOfWeek(jsDay) {
    if (jsDay === 0)
        return 7;
    if (jsDay === 1)
        return 1;
    if (jsDay === 2)
        return 2;
    if (jsDay === 3)
        return 3;
    if (jsDay === 4)
        return 4;
    if (jsDay === 5)
        return 5;
    return 6;
}
