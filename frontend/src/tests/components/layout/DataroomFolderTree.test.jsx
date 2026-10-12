import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import DataroomFolderTree from '../../../components/layout/DataroomFolderTree';
import * as api from '../../../services/api';
import '../../../i18n';

vi.mock('../../../services/api', () => ({
  getDataroom: vi.fn(),
  getDataroomFolders: vi.fn(),
  getDataroomFolderContents: vi.fn(),
}));

const DR = 'dr_1';

// The flat folder list the component receives from /dataroom-folders/.
const flatFolders = [
  { id: 'f_alpha', name: 'Alpha', dataroom: DR, parent: null },
  { id: 'f_alpha1', name: 'Alpha-1', dataroom: DR, parent: 'f_alpha' },
  { id: 'f_alpha2', name: 'Alpha-2', dataroom: DR, parent: 'f_alpha1' },
  { id: 'f_beta', name: 'Beta', dataroom: DR, parent: null },
];

// Rows are 32px divs; every folder row carries its own expand/collapse button,
// so a bare getByLabelText('Expand folder') matches one per folder. Scope to the row.
const folderRow = (name) => screen.getByText(name).closest('div[role="button"]');
const toggleFor = (name, label = 'Expand folder') =>
  within(folderRow(name)).getByRole('button', { name: label });

function renderTree(initialPath = `/datarooms/${DR}`) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/datarooms/:dataroomId" element={<DataroomFolderTree />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('DataroomFolderTree', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getDataroom.mockResolvedValue({
      // Root scope: 3 documents live directly at the dataroom root, plus 2 folders.
      data: {
        items: [
          { id: 'd1', type: 'document' },
          { id: 'd2', type: 'document' },
          { id: 'd3', type: 'document' },
          { id: 'f_alpha', type: 'folder' },
          { id: 'f_beta', type: 'folder' },
        ],
      },
    });
    api.getDataroomFolders.mockResolvedValue({ data: flatFolders });
    api.getDataroomFolderContents.mockResolvedValue({ data: { documents: [] } });
  });

  it('renders nothing when there is no dataroom in the route', () => {
    render(
      <MemoryRouter initialEntries={['/documents']}>
        <DataroomFolderTree />
      </MemoryRouter>
    );
    expect(screen.queryByText('Folders')).not.toBeInTheDocument();
  });

  it('shows a root "All files" row counting only root documents, not folders', async () => {
    renderTree();
    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());

    // Root count comes from getDataroom items filtered to type === 'document'.
    // 3 documents + 2 folders in the payload must yield 3, not 5.
    expect(await screen.findByText('3')).toBeInTheDocument();
    expect(screen.getByText('All files')).toBeInTheDocument();
  });

  it('renders root folders but keeps children hidden until the parent is expanded', async () => {
    const user = userEvent.setup();
    renderTree();
    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());

    expect(screen.getByText('Beta')).toBeInTheDocument();
    // Children are collapsed by default.
    expect(screen.queryByText('Alpha-1')).not.toBeInTheDocument();

    await user.click(toggleFor('Alpha'));
    expect(await screen.findByText('Alpha-1')).toBeInTheDocument();
    // Still collapsed one level deeper.
    expect(screen.queryByText('Alpha-2')).not.toBeInTheDocument();
  });

  it('indents children deeper than their parent', async () => {
    const user = userEvent.setup();
    renderTree();
    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());

    await user.click(toggleFor('Alpha'));
    const alpha1 = await screen.findByText('Alpha-1');
    await user.click(toggleFor('Alpha-1'));
    const alpha2 = await screen.findByText('Alpha-2');

    const pad = (node) =>
      parseInt(node.closest('div[role="button"]').style.paddingLeft, 10);
    expect(pad(alpha2)).toBeGreaterThan(pad(alpha1));
    expect(pad(alpha1)).toBeGreaterThan(pad(screen.getByText('Alpha')));
  });

  it('fetches a folder document count on expand and renders it as a bare tabular numeral', async () => {
    const user = userEvent.setup();
    api.getDataroomFolderContents.mockResolvedValue({
      data: { documents: [{ id: 'x' }, { id: 'y' }] },
    });
    renderTree();
    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());

    // Not fetched while collapsed.
    expect(api.getDataroomFolderContents).not.toHaveBeenCalled();

    await user.click(toggleFor('Alpha'));
    const count = await screen.findByText('2');

    expect(api.getDataroomFolderContents).toHaveBeenCalledWith('f_alpha');
    // 002 spec: counts are plain tabular numbers, never pills or badges.
    expect(count.className).toContain('tnum');
    expect(count.className).not.toMatch(/rounded-full|badge|pill/);
    expect(count.tagName).toBe('SPAN');
  });

  it('caches the count and does not refetch on repeated expands', async () => {
    const user = userEvent.setup();
    renderTree();
    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());

    await user.click(toggleFor('Alpha'));
    await screen.findByText('Beta');
    await user.click(toggleFor('Alpha', 'Collapse folder'));
    await user.click(toggleFor('Alpha'));

    await waitFor(() =>
      expect(api.getDataroomFolderContents).toHaveBeenCalledTimes(1)
    );
  });

  it('shows "No folders yet" while still showing the root row when a dataroom has no folders', async () => {
    api.getDataroomFolders.mockResolvedValue({ data: [] });
    renderTree();
    expect(await screen.findByText('No folders yet')).toBeInTheDocument();
    // The root scope row must survive an empty folder list, otherwise loose
    // root-level documents would be invisible in the tree.
    expect(screen.getByText('All files')).toBeInTheDocument();
  });

  it('falls back to a zero root count when getDataroom rejects', async () => {
    api.getDataroom.mockRejectedValue(new Error('boom'));
    renderTree();
    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());
    // Count component renders nothing for a falsy/zero count.
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });
});
