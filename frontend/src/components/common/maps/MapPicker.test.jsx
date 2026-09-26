import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';


const clickHandlers = [];
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children, ...rest }) => (
    <div data-testid="map" {...rest}>
      {children}
    </div>
  ),
  TileLayer: () => null,
  Marker: ({ position }) => <div data-testid="marker" data-position={position.join(',')} />,
  useMapEvents: (handlers) => {
    clickHandlers.push(handlers.click);
    return null;
  },
}));

const { MapPicker } = await import('./MapPicker');

function clickMapAt(lat, lng) {
  clickHandlers.at(-1)({ latlng: { lat, lng } });
}

describe('MapPicker', () => {
  it('reports the point that was clicked, rounded to six decimals', async () => {
    const onChange = vi.fn();
    render(<MapPicker latitude={10.7} longitude={106.7} onChange={onChange} />);

    clickMapAt(10.7723456789, 106.6987654321);

    expect(onChange).toHaveBeenCalledWith({ latitude: 10.772346, longitude: 106.698765 });
  });

  it('shows the current point so the value can be checked without reading the pin', () => {
    render(<MapPicker latitude={10.772345} longitude={106.698765} onChange={() => {}} />);

    expect(screen.getByText(/10\.772345/)).toBeInTheDocument();
    expect(screen.getByText(/106\.698765/)).toBeInTheDocument();
  });

  it('drops no pin until a point is chosen', () => {
    render(<MapPicker latitude={null} longitude={null} onChange={() => {}} />);

    expect(screen.queryByTestId('marker')).not.toBeInTheDocument();
    expect(screen.getByText(/no location chosen/i)).toBeInTheDocument();
  });

  it('places the pin at the value it was given', () => {
    render(<MapPicker latitude={10.5} longitude={106.5} onChange={() => {}} />);

    expect(screen.getByTestId('marker')).toHaveAttribute('data-position', '10.5,106.5');
  });

  it('clears the point when asked', async () => {
    const onChange = vi.fn();
    render(<MapPicker latitude={10.5} longitude={106.5} onChange={onChange} />);

    await userEvent.click(screen.getByRole('button', { name: /clear/i }));

    
    expect(onChange).toHaveBeenCalledWith({ latitude: null, longitude: null });
  });

  it('ignores clicks when it is read-only', () => {
    const onChange = vi.fn();
    render(<MapPicker latitude={10.5} longitude={106.5} onChange={onChange} readOnly />);

    clickMapAt(11, 107);

    expect(onChange).not.toHaveBeenCalled();
  });
});
