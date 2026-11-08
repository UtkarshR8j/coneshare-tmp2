import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AssetsBrowserDialog } from '../../../components/dialogs/AssetsBrowserDialog';
import * as api from '../../../services/api';
import '../../../i18n';

vi.mock('../../../services/api');
vi.stubGlobal('ResizeObserver', vi.fn(() => ({ observe: vi.fn(), unobserve: vi.fn(), disconnect: vi.fn() })));

const file = { space_id: 'users:u1', path: 'top.pdf', name: 'top.pdf', type: 'file', size: 10, doc_type: 'pdf' };
const folder = { space_id: 'users:u1', path: 'Invoices', name: 'Invoices', type: 'folder', size: null };
const inner = { space_id: 'users:u1', path: 'Invoices/inv.pdf', name: 'inv.pdf', type: 'file', size: 5, doc_type: 'pdf' };

describe('AssetsBrowserDialog', () => {
  const onAdded = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    api.getAssetSpaces.mockResolvedValue({ data: [{ id: 'users:u1', name: 'Utkarsh', kind: 'personal' }] });
    api.browseAssets.mockImplementation((_, path) =>
      Promise.resolve({ data: { items: path === 'Invoices' ? [inner] : [folder, file] } }));
    api.addAssetsToDataroom.mockResolvedValue({ data: { snapshots: [{ id: 's1', status: 'queued' }, { id: 's2', status: 'queued' }] } });
    api.getAssetSnapshots.mockResolvedValue({ data: [{ id: 's1', status: 'ready' }, { id: 's2', status: 'ready' }] });
  });

  const open = () => render(
    <AssetsBrowserDialog isOpen onOpenChange={vi.fn()} dataroomId="dr1" destinationFolderId="f1" onAdded={onAdded} />
  );

  it('lists the first space on open', async () => {
    open();
    expect(await screen.findByText('top.pdf')).toBeInTheDocument();
    expect(api.browseAssets).toHaveBeenCalledWith('users:u1', '');
  });

  it('keeps selection across folders and submits every picked file', async () => {
    const user = userEvent.setup();
    open();
    await screen.findByText('top.pdf');
    await user.click(screen.getByLabelText('top.pdf'));
    await user.click(screen.getByRole('button', { name: 'Invoices' }));
    await screen.findByText('inv.pdf');
    await user.click(screen.getByLabelText('inv.pdf'));
    await user.click(screen.getByTestId('assets-add-confirm'));
    await waitFor(() => expect(api.addAssetsToDataroom).toHaveBeenCalledWith(
      'dr1',
      [{ space_id: 'users:u1', path: 'top.pdf' }, { space_id: 'users:u1', path: 'Invoices/inv.pdf' }],
      'f1',
    ));
    await waitFor(() => expect(onAdded).toHaveBeenCalled());
  });

  it('searches after typing', async () => {
    const user = userEvent.setup();
    api.searchAssets.mockResolvedValue({ data: { items: [inner], truncated: false } });
    open();
    await screen.findByText('top.pdf');
    await user.type(screen.getByTestId('assets-search'), 'inv');
    expect(await screen.findByText('Invoices/inv.pdf')).toBeInTheDocument();
    expect(api.searchAssets).toHaveBeenCalledWith('inv', null);
  });

  it('returns to the folder listing when the search drops below two characters', async () => {
    const user = userEvent.setup();
    api.searchAssets.mockResolvedValue({ data: { items: [inner], truncated: false } });
    open();
    await screen.findByText('top.pdf');
    await user.type(screen.getByTestId('assets-search'), 'in');
    await screen.findByText('Invoices/inv.pdf');
    await user.type(screen.getByTestId('assets-search'), '{Backspace}');
    expect(await screen.findByText('top.pdf')).toBeInTheDocument();
  });

  it('previews a supported file through an object URL', async () => {
    const user = userEvent.setup();
    const preview = { close: vi.fn(), location: '' };
    vi.spyOn(window, 'open').mockReturnValue(preview);
    URL.createObjectURL = vi.fn(() => 'blob:preview');
    URL.revokeObjectURL = vi.fn();
    api.previewAsset.mockResolvedValue({ data: new Blob(['x'], { type: 'application/pdf' }) });
    open();
    await screen.findByText('top.pdf');
    await user.click(screen.getByRole('button', { name: 'Preview top.pdf' }));
    expect(api.previewAsset).toHaveBeenCalledWith('users:u1', 'top.pdf');
    await waitFor(() => expect(preview.location).toBe('blob:preview'));
  });

  it('offers no preview for unsupported types and closes the window if a preview fails', async () => {
    const user = userEvent.setup();
    const preview = { close: vi.fn(), location: '' };
    vi.spyOn(window, 'open').mockReturnValue(preview);
    api.previewAsset.mockRejectedValue(new Error('nope'));
    api.browseAssets.mockResolvedValue({ data: { items: [file, { ...file, path: 'page.html', name: 'page.html', doc_type: 'file' }] } });
    open();
    await screen.findByText('page.html');
    expect(screen.queryByRole('button', { name: 'Preview page.html' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Preview top.pdf' }));
    await waitFor(() => expect(preview.close).toHaveBeenCalled());
  });

  it('shows a retry when the listing fails', async () => {
    api.getAssetSpaces.mockRejectedValue({ response: { status: 503, data: { detail: 'not configured' } } });
    open();
    expect(await screen.findByTestId('assets-error')).toBeInTheDocument();
  });
});
