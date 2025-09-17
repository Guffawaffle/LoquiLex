import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ModelSelect } from '../ModelSelect';

// Mock fetch
(globalThis as any).fetch = vi.fn();

const mockAsrModels = [
  { id: 'tiny.en', name: 'Tiny English', size: '39MB', available: true },
  { id: 'base.en', name: 'Base English', size: '74MB', available: true },
];

const mockMtModels = [
  { id: 'nllb-200-600M', name: 'NLLB 600M', size: '2.4GB', available: true },
];

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  );
};

beforeEach(() => {
  ((globalThis as any).fetch as any).mockClear();
});

test('renders model selection interface', async () => {
  ((globalThis as any).fetch as any)
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockAsrModels),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockMtModels),
    });

  renderWithRouter(<ModelSelect />);
  
  expect(screen.getByText('Loading Models...')).toBeInTheDocument();
  
  await waitFor(() => {
    expect(screen.getByText('LoquiLex')).toBeInTheDocument();
  });
  
  expect(screen.getByText('Live captioning and translation - local-first and offline-ready')).toBeInTheDocument();
  expect(screen.getByText('ASR Model')).toBeInTheDocument();
  expect(screen.getByText('Tiny English')).toBeInTheDocument();
});

test('handles model loading error', async () => {
  ((globalThis as any).fetch as any).mockRejectedValue(new Error('Network error'));

  renderWithRouter(<ModelSelect />);
  
  await waitFor(() => {
<<<<<<< HEAD
    expect(screen.getByText('Network error')).toBeInTheDocument();
=======
    expect(screen.getByText('Failed to load models')).toBeInTheDocument();
>>>>>>> a96258d (Implement FastAPI single-server with React SPA and baseline UI components)
  });
});

test('shows translation options when enabled', async () => {
  ((globalThis as any).fetch as any)
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockAsrModels),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockMtModels),
    });

  renderWithRouter(<ModelSelect />);
  
  await waitFor(() => {
    expect(screen.getByText('Enable Translation')).toBeInTheDocument();
  });
  
  // Translation should be enabled by default
  expect(screen.getByText('Translation Model')).toBeInTheDocument();
  expect(screen.getByText('Target Language')).toBeInTheDocument();
});