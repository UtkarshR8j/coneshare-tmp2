import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, ChevronRight, Eye, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '../ui/Dialog';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { Input } from '../ui/Input';
import { FileTypeIcon } from '../documents/FileTypeIcon';
import { formatBytes } from '../../lib/formatters';
import { addAssetsToDataroom, browseAssets, getAssetSnapshots, getAssetSpaces, previewAsset, searchAssets } from '../../services/api';
import { getLocalizedErrorMessage } from '../../utils/errorTranslator';

const POLL_MS = 2000;
const POLL_LIMIT = 150; // about 5 minutes
const SEARCH_DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 2;
const PREVIEWABLE = /\.(pdf|png|jpe?g|gif|webp)$/i; // mirrors PREVIEW_CONTENT_TYPES in assetbrowser/views.py
const PREVIEW_URL_LIFETIME_MS = 60000;
const keyOf = (item) => `${item.space_id}|${item.path}`;
const isFinished = (snapshot) => snapshot.status === 'ready' || snapshot.status === 'failed';

export function AssetsBrowserDialog({ isOpen, onOpenChange, dataroomId, destinationFolderId, onAdded }) {
  const { t } = useTranslation();
  const [spaces, setSpaces] = useState([]);
  const [spaceId, setSpaceId] = useState(null);
  const [path, setPath] = useState('');
  const [items, setItems] = useState([]);
  const [query, setQuery] = useState('');
  const [truncated, setTruncated] = useState(false);
  const [selection, setSelection] = useState(new Map());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const cancelled = useRef(false);

  const fail = useCallback((err) => setError(getLocalizedErrorMessage(err, 'assetsBrowser.failedToLoad')), []);

  const browse = useCallback(async (nextSpaceId, nextPath) => {
    setLoading(true);
    setError(null);
    setTruncated(false);
    try {
      const response = await browseAssets(nextSpaceId, nextPath);
      setItems(response.data.items);
      setSpaceId(nextSpaceId);
      setPath(nextPath);
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }, [fail]);

  const loadSpaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getAssetSpaces();
      setSpaces(response.data);
      if (response.data.length > 0) {
        await browse(response.data[0].id, '');
      }
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }, [browse, fail]);

  useEffect(() => {
    if (!isOpen) return undefined;
    cancelled.current = false;
    setSelection(new Map());
    setQuery('');
    loadSpaces();
    return () => {
      cancelled.current = true;
    };
  }, [isOpen, loadSpaces]);

  useEffect(() => {
    const trimmed = query.trim();
    if (!isOpen || trimmed.length < MIN_QUERY_LENGTH) return undefined;
    const timer = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await searchAssets(trimmed, null);
        setItems(response.data.items);
        setTruncated(response.data.truncated);
      } catch (err) {
        fail(err);
      } finally {
        setLoading(false);
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query, isOpen, fail]);

  const handleQueryChange = (value) => {
    const wasSearching = query.trim().length >= MIN_QUERY_LENGTH;
    setQuery(value);
    if (wasSearching && value.trim().length < MIN_QUERY_LENGTH && spaceId) browse(spaceId, path);
  };

  const toggle = (item) => {
    setSelection((prev) => {
      const next = new Map(prev);
      if (next.has(keyOf(item))) next.delete(keyOf(item));
      else next.set(keyOf(item), item);
      return next;
    });
  };

  const handlePreview = async (item) => {
    const previewWindow = window.open('', '_blank'); // must open inside the click, or popup blockers refuse it
    try {
      const { data } = await previewAsset(item.space_id, item.path);
      const url = URL.createObjectURL(data);
      if (previewWindow) previewWindow.location = url;
      setTimeout(() => URL.revokeObjectURL(url), PREVIEW_URL_LIFETIME_MS);
    } catch (err) {
      previewWindow?.close();
      console.error('Failed to preview asset:', err); // toast comes from the api interceptor
    }
  };

  const waitForSnapshots = async (ids) => {
    for (let attempt = 0; attempt < POLL_LIMIT && !cancelled.current; attempt += 1) {
      const { data } = await getAssetSnapshots(dataroomId, ids);
      if (data.length === ids.length && data.every(isFinished)) return data;
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    }
    return null;
  };

  const handleConfirm = async () => {
    setIsConfirming(true);
    try {
      const picked = [...selection.values()].map(({ space_id, path: itemPath }) => ({ space_id, path: itemPath }));
      const { data } = await addAssetsToDataroom(dataroomId, picked, destinationFolderId || null);
      const results = await waitForSnapshots(data.snapshots.map((s) => s.id));
      if (results === null) {
        toast.info(t('assetsBrowser.stillCopying'));
      } else {
        const failed = results.filter((s) => s.status === 'failed');
        if (failed.length > 0) toast.error(t('assetsBrowser.someFailed', { count: failed.length, reason: failed[0].error }));
        else toast.success(t('assetsBrowser.added', { count: results.length }));
      }
      onAdded();
      onOpenChange(false);
    } catch (err) {
      console.error('Failed to add assets:', err); // toast comes from the api interceptor
    } finally {
      setIsConfirming(false);
    }
  };

  const segments = path.split('/').filter(Boolean);
  const isSearching = query.trim().length >= MIN_QUERY_LENGTH;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!isConfirming) onOpenChange(open); }}>
      <DialogContent className="sm:max-w-3xl h-[75vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>{t('assetsBrowser.title')}</DialogTitle>
          <DialogDescription>{t('assetsBrowser.description')}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label={t('assetsBrowser.space')}
            className="h-10 rounded-md border border-gray-300 bg-transparent px-2 text-sm dark:border-gray-700"
            value={spaceId || ''}
            onChange={(e) => { setQuery(''); browse(e.target.value, ''); }}
          >
            {spaces.map((space) => <option key={space.id} value={space.id}>{space.name}</option>)}
          </select>
          <Input
            data-testid="assets-search"
            className="flex-1 min-w-48"
            placeholder={t('assetsBrowser.searchPlaceholder')}
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
          />
        </div>

        {!isSearching && (
          <nav className="flex flex-wrap items-center gap-1 text-sm" aria-label="Breadcrumb">
            <button type="button" className="text-gray-500 hover:text-gray-800" onClick={() => browse(spaceId, '')}>
              {t('assetsBrowser.root')}
            </button>
            {segments.map((segment, index) => (
              <span key={segments.slice(0, index + 1).join('/')} className="flex items-center gap-1">
                <ChevronRight className="h-4 w-4 text-gray-400" />
                <button type="button" className="text-gray-500 hover:text-gray-800" onClick={() => browse(spaceId, segments.slice(0, index + 1).join('/'))}>
                  {segment}
                </button>
              </span>
            ))}
          </nav>
        )}

        <div className="flex-grow overflow-y-auto rounded-md border p-1">
          {loading ? (
            <div className="flex h-full items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-gray-500" /></div>
          ) : error ? (
            <div data-testid="assets-error" className="flex h-full flex-col items-center justify-center p-4 text-center">
              <AlertTriangle className="mb-2 h-8 w-8 text-destructive" />
              <p className="text-sm text-muted-foreground">{error}</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={loadSpaces}>{t('cloudImport.retry')}</Button>
            </div>
          ) : items.length === 0 ? (
            <p className="py-8 text-center text-gray-500">{t('assetsBrowser.empty')}</p>
          ) : (
            <ul className="space-y-1">
              {items.map((item) => (
                <li key={keyOf(item)} className="flex items-center gap-3 rounded-md p-2 hover:bg-gray-100 dark:hover:bg-gray-800">
                  {item.type === 'folder' ? (
                    <button type="button" className="flex w-full items-center gap-3 text-left" onClick={() => browse(item.space_id, item.path)}>
                      <FileTypeIcon type="folder" className="h-5 w-5 shrink-0" />
                      <span className="flex-grow">{item.name}</span>
                    </button>
                  ) : (
                    <>
                      <Checkbox id={keyOf(item)} aria-label={item.name} checked={selection.has(keyOf(item))} onCheckedChange={() => toggle(item)} />
                      <FileTypeIcon type={item.doc_type} className="h-5 w-5 shrink-0" />
                      <span className="flex-grow truncate" title={item.path}>{isSearching ? item.path : item.name}</span>
                      <span className="text-xs text-gray-500">{formatBytes(item.size)}</span>
                      {PREVIEWABLE.test(item.name) && (
                        <button
                          type="button"
                          className="shrink-0 text-gray-500 hover:text-gray-800"
                          aria-label={`${t('assetsBrowser.preview')} ${item.name}`}
                          title={t('assetsBrowser.preview')}
                          onClick={() => handlePreview(item)}
                        >
                          <Eye className="h-4 w-4" />
                        </button>
                      )}
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
        {truncated && <p className="text-xs text-amber-700">{t('assetsBrowser.truncated')}</p>}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isConfirming}>{t('common.cancel')}</Button>
          <Button data-testid="assets-add-confirm" onClick={handleConfirm} disabled={isConfirming || selection.size === 0}>
            {isConfirming ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />{t('assetsBrowser.copying')}</> : t('assetsBrowser.addSelected', { count: selection.size })}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
