import "@testing-library/jest-dom";
import { vi } from 'vitest';

// Mock ResizeObserver for Radix UI components
const ResizeObserverMock = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

vi.stubGlobal('ResizeObserver', ResizeObserverMock);
vi.stubGlobal('DOMMatrix', class DOMMatrix {});

// Mock window.matchMedia for jsdom. Radix UI (used by shadcn components) and
// responsive logic call matchMedia; jsdom implements neither, so without this
// every component under test throws "window.matchMedia is not a function".
vi.stubGlobal('matchMedia', vi.fn((query) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
})));
