import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChevronRight, Folder, FolderOpen, FileText } from 'lucide-react';
import { getDataroom, getDataroomFolders, getDataroomFolderContents } from '../../services/api';
import { cn } from '../../lib/utils';

// Scoped to ONE dataroom: a dataroom is shared with a single recipient, so a tree
// fanning out across multiple datarooms would be a comparison view nobody needs.
// This renders the folder tree of the dataroom you are currently inside, and
// nothing at all when you are not inside one.

// Turns the flat /dataroom-folders/ list (each folder carries its `parent` id)
// into a nested tree. Folders whose parent id is not in the set are roots.
function buildFolderTree(folders) {
  const byId = new Map();
  const roots = [];
  folders.forEach((f) => byId.set(String(f.id), { ...f, children: [] }));
  folders.forEach((f) => {
    const node = byId.get(String(f.id));
    const parentId = f.parent ? String(f.parent) : null;
    const parent = parentId ? byId.get(parentId) : null;
    if (parent) {
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

// A count is always a bare tabular numeral in muted text (002: "counts as plain
// tabular numbers instead of pills"). Never a badge, never a pill.
function Count({ value }) {
  if (!value) return null;
  return (
    <span className="tnum ml-auto shrink-0 pl-2 text-[11px] font-normal text-muted-foreground/70">
      {value}
    </span>
  );
}

function FolderNode({ node, dataroomId, level }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [expanded, setExpanded] = useState(false);
  // Document counts are not in the flat folder list; they come back from the folder
  // retrieve endpoint. Fetched on first expand, then cached in state.
  const [docCount, setDocCount] = useState(null);

  const childCount = node.children.length;
  const active =
    location.pathname === `/datarooms/${dataroomId}` &&
    new URLSearchParams(location.search).get('folder') === String(node.id);

  const toggle = useCallback((event) => {
    event.stopPropagation();
    setExpanded((prev) => !prev);
  }, []);

  const open = useCallback(() => {
    navigate(`/datarooms/${dataroomId}?folder=${node.id}`);
  }, [navigate, dataroomId, node.id]);

  useEffect(() => {
    if (!expanded || docCount !== null) return;
    let cancelled = false;
    getDataroomFolderContents(node.id)
      .then((response) => {
        if (!cancelled) setDocCount(response.data?.documents?.length ?? 0);
      })
      .catch(() => {
        if (!cancelled) setDocCount(0);
      });
    return () => {
      cancelled = true;
    };
  }, [expanded, docCount, node.id]);

  return (
    <li>
      <div
        role="button"
        tabIndex={0}
        onClick={open}
        onKeyDown={(e) => e.key === 'Enter' && open()}
        style={{ paddingLeft: `${12 + level * 14}px` }}
        className={cn(
          'flex h-8 w-full cursor-pointer items-center rounded-lg pr-3 text-[13px] transition-colors',
          active
            ? 'bg-primary/12 font-medium text-primary'
            : 'text-foreground/85 hover:bg-secondary'
        )}
      >
        <button
          type="button"
          onClick={toggle}
          aria-label={expanded ? 'Collapse folder' : 'Expand folder'}
          className={cn(
            'mr-1 flex h-4 w-4 shrink-0 items-center justify-center text-muted-foreground transition-transform hover:text-foreground',
            !childCount && 'invisible',
            expanded && 'rotate-90'
          )}
        >
          <ChevronRight className="h-3 w-3" />
        </button>
        {expanded ? (
          <FolderOpen className="mr-2 h-3.5 w-3.5 shrink-0" />
        ) : (
          <Folder className="mr-2 h-3.5 w-3.5 shrink-0" />
        )}
        <span className="truncate">{node.name}</span>
        {docCount > 0 && (
          <FileText className="ml-1.5 h-3 w-3 shrink-0 text-muted-foreground/60" />
        )}
        <Count value={docCount} />
      </div>

      {expanded && childCount > 0 && (
        <ul>
          {node.children.map((child) => (
            <FolderNode
              key={child.id}
              node={child}
              dataroomId={dataroomId}
              level={level + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function DataroomFolderTree() {
  const { t } = useTranslation();
  const { dataroomId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [roots, setRoots] = useState(null);
  // Documents sitting directly at the dataroom root (folder=null) are NOT in the
  // folder list. Without a root row they would be invisible here while showing in
  // the main pane, so the root scope gets its own row and its own count.
  const [rootDocCount, setRootDocCount] = useState(null);

  const rootActive =
    Boolean(dataroomId) &&
    location.pathname === `/datarooms/${dataroomId}` &&
    !new URLSearchParams(location.search).get('folder');

  useEffect(() => {
    if (!dataroomId) return;
    let cancelled = false;
    setRoots(null);
    getDataroom(dataroomId)
      .then((response) => {
        if (cancelled) return;
        const items = response.data?.items ?? [];
        setRootDocCount(items.filter((item) => item.type === 'document').length);
      })
      .catch(() => {
        if (!cancelled) setRootDocCount(0);
      });
    getDataroomFolders(dataroomId)
      .then((response) => {
        if (cancelled) return;
        const folders = response.data?.results ?? response.data ?? [];
        setRoots(buildFolderTree(folders));
      })
      .catch(() => {
        if (!cancelled) setRoots([]);
      });
    return () => {
      cancelled = true;
    };
  }, [dataroomId]);

  const nodes = useMemo(() => roots ?? [], [roots]);

  if (!dataroomId) return null;

  return (
    <div className="mt-5 border-t border-border pt-4">
      <h3 className="px-4 pb-2 text-[11px] font-medium uppercase tracking-[0.09em] text-muted-foreground">
        {t('nav.folders', { defaultValue: 'Folders' })}
      </h3>
      {/* The dataroom root scope: holds loose files that live in no folder. */}
      <ul className="pr-2">
        <li>
          <div
            role="button"
            tabIndex={0}
            onClick={() => navigate(`/datarooms/${dataroomId}`)}
            onKeyDown={(e) => e.key === 'Enter' && navigate(`/datarooms/${dataroomId}`)}
            className={cn(
              'flex h-8 w-full cursor-pointer items-center rounded-lg pr-3 text-[13px] transition-colors',
              rootActive
                ? 'bg-primary/12 font-medium text-primary'
                : 'text-foreground/85 hover:bg-secondary'
            )}
            style={{ paddingLeft: '12px' }}
          >
            <span className="mr-1 w-4 shrink-0" />
            <FileText className="mr-2 h-3.5 w-3.5 shrink-0" />
            <span className="truncate">
              {t('nav.allFiles', { defaultValue: 'All files' })}
            </span>
            <Count value={rootDocCount} />
          </div>
        </li>
      </ul>

      {roots === null && (
        <p className="px-4 pt-2 text-[12px] leading-8 text-muted-foreground/60">Loading</p>
      )}
      {roots !== null && nodes.length === 0 && (
        <p className="px-4 pt-2 text-[12px] leading-8 text-muted-foreground/60">
          {t('nav.noFolders', { defaultValue: 'No folders yet' })}
        </p>
      )}
      {nodes.length > 0 && (
        <ul className="pr-2">
          {nodes.map((node) => (
            <FolderNode key={node.id} node={node} dataroomId={dataroomId} level={0} />
          ))}
        </ul>
      )}
    </div>
  );
}

export default DataroomFolderTree;
