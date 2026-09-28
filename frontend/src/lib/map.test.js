import L from 'leaflet';
import { describe, expect, it } from 'vitest';

import { OSM_ATTRIBUTION, OSM_TILE_URL } from './map';

describe('shared map setup', () => {
  it('uses exactly the tile URL the OSM tile policy asks for', () => {
    expect(OSM_TILE_URL).toBe('https://tile.openstreetmap.org/{z}/{x}/{y}.png');
  });

  it('credits OpenStreetMap on every map', () => {
    expect(OSM_ATTRIBUTION).toContain('OpenStreetMap');
    expect(OSM_ATTRIBUTION).toContain('https://www.openstreetmap.org/copyright');
  });

  it('gives the default pin its image as-is, with no folder guessed in front', () => {
    const icon = new L.Icon.Default();
    const url = icon._getIconUrl('icon');
    expect(url).toBe(L.Icon.Default.prototype.options.iconUrl);
    expect(url).not.toMatch(/^.+(data:|\/assets\/).*(data:|\/assets\/)/);
  });
});
