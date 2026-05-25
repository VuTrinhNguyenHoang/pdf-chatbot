'use client';

import { useState, useEffect, useCallback } from 'react';
import type { ElementType } from 'react';
import { FileText, Table2, Image, RefreshCw, Trash2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/hooks/use-toast';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type {
  ContentEntry,
  ContentResponse,
  DeleteContentResponse,
  FileEntry,
} from '@/app/api/content/route';

type Tab = 'files' | 'tables' | 'images';

const TABS: { id: Tab; label: string; icon: ElementType }[] = [
  { id: 'files', label: 'Files', icon: FileText },
  { id: 'tables', label: 'Tables', icon: Table2 },
  { id: 'images', label: 'Images', icon: Image },
];

// ── File list ──────────────────────────────────────────────────────────────

function FilesList({
  files,
  deletingFilename,
  onDeleteClick,
}: {
  files: FileEntry[];
  deletingFilename: string | null;
  onDeleteClick: (file: FileEntry) => void;
}) {
  if (!files.length) {
    return <Empty text="No files ingested yet" />;
  }
  return (
    <div className="space-y-1">
      {files.map((f) => (
        <div
          key={f.filename}
          className="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted"
        >
          <div className="min-w-0 flex-1 cursor-default">
            <p className="text-xs font-medium truncate" title={f.filename}>{f.filename}</p>
            <p className="text-[10px] text-muted-foreground">
              {f.chunks} chunks · {f.tables} tables · {f.images} images
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
            onClick={() => onDeleteClick(f)}
            disabled={deletingFilename === f.filename}
            title={`Delete ${f.filename}`}
          >
            {deletingFilename === f.filename ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Trash2 className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      ))}
    </div>
  );
}

// ── Markdown table renderer ────────────────────────────────────────────────

function MarkdownTable({ content }: { content: string }) {
  const lines = content.split('\n').filter((l) => l.trim().startsWith('|'));
  if (lines.length < 2) {
    return (
      <pre className="text-xs font-mono bg-muted/40 rounded-md p-3 overflow-x-auto whitespace-pre-wrap">
        {content}
      </pre>
    );
  }

  const parseRow = (line: string) =>
    line.split('|').slice(1, -1).map((cell) => cell.trim());
  const isSeparator = (line: string) => /^[\s|:-]+$/.test(line);

  const dataLines = lines.filter((l) => !isSeparator(l));
  const [headerLine, ...bodyLines] = dataLines;
  const headers = parseRow(headerLine);
  const rows = bodyLines.map(parseRow);

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="bg-muted/60">
            {headers.map((h, i) => (
              <th key={i} className="px-3 py-2 text-left font-semibold border-b whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className={cn(ri % 2 === 0 ? 'bg-white' : 'bg-muted/20', 'hover:bg-muted/40')}>
              {headers.map((_, ci) => (
                <td key={ci} className="px-3 py-1.5 border-b border-border/50 align-top">
                  {row[ci] ?? ''}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Table list ─────────────────────────────────────────────────────────────

function TablesList({ tables }: { tables: ContentEntry[] }) {
  const [selected, setSelected] = useState<ContentEntry | null>(null);

  if (!tables.length) return <Empty text="No tables extracted" />;

  return (
    <>
      <div className="space-y-1">
        {tables.map((t) => (
          <button
            key={t.id}
            onClick={() => setSelected(t)}
            className="w-full text-left px-2 py-1.5 rounded-md hover:bg-muted transition-colors group"
          >
            <p className="text-xs font-medium truncate group-hover:text-foreground">
              {t.title || t.filename}
            </p>
            <p className="text-[10px] text-muted-foreground">p.{t.page ?? '?'}</p>
          </button>
        ))}
      </div>

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{selected?.title || selected?.filename}</DialogTitle>
            <DialogDescription>
              {selected?.filename} · page {selected?.page ?? '?'}
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            <MarkdownTable content={selected?.content ?? ''} />
          </DialogBody>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── Image list ─────────────────────────────────────────────────────────────

function ImagesList({ images }: { images: ContentEntry[] }) {
  const [selected, setSelected] = useState<ContentEntry | null>(null);

  if (!images.length) return <Empty text="No images extracted" />;

  return (
    <>
      <div className="space-y-1">
        {images.map((img) => (
          <button
            key={img.id}
            onClick={() => setSelected(img)}
            className="w-full text-left px-2 py-1.5 rounded-md hover:bg-muted transition-colors group"
          >
            <p className="text-xs font-medium truncate group-hover:text-foreground">
              {img.title || img.filename}
            </p>
            <p className="text-[10px] text-muted-foreground">
              p.{img.page ?? '?'}
              {img.imageStatus && img.imageStatus !== 'extracted' ? ' · no preview' : ''}
            </p>
          </button>
        ))}
      </div>

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{selected?.title || selected?.filename}</DialogTitle>
            <DialogDescription>
              {selected?.filename} · page {selected?.page ?? '?'}
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            {selected?.imageUrl ? (
              <div className="overflow-hidden rounded-md border bg-white">
                <img
                  src={selected.imageUrl}
                  alt={selected.title || selected.filename}
                  className="max-h-[60vh] w-full object-contain"
                />
              </div>
            ) : (
              <div className="rounded-md border bg-muted/40 p-4 text-sm text-muted-foreground">
                Image preview unavailable.
              </div>
            )}
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              {selected?.content || 'No description available.'}
            </p>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── Shared ─────────────────────────────────────────────────────────────────

function Empty({ text }: { text: string }) {
  return <p className="text-xs text-muted-foreground px-2 py-6 text-center">{text}</p>;
}

// ── Sidebar ────────────────────────────────────────────────────────────────

interface KnowledgeSidebarProps {
  refreshTrigger?: number;
  onDocumentDeleted?: (filename: string) => void;
}

export function KnowledgeSidebar({ refreshTrigger, onDocumentDeleted }: KnowledgeSidebarProps) {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<Tab>('files');
  const [data, setData] = useState<ContentResponse>({ files: [], tables: [], images: [] });
  const [loading, setLoading] = useState(false);
  const [deletingFilename, setDeletingFilename] = useState<string | null>(null);
  const [fileToDelete, setFileToDelete] = useState<FileEntry | null>(null);

  const fetchContent = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/content', { cache: 'no-store' });
      if (res.ok) setData(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchContent(); }, [fetchContent, refreshTrigger]);

  const deleteFile = async () => {
    if (!fileToDelete) return;

    setDeletingFilename(fileToDelete.filename);
    try {
      const res = await fetch('/api/content', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: fileToDelete.filename }),
      });
      const payload = await res.json() as DeleteContentResponse | { error: string };

      if (!res.ok) {
        throw new Error('error' in payload ? payload.error : 'Failed to delete file');
      }

      onDocumentDeleted?.(fileToDelete.filename);
      setFileToDelete(null);
      await fetchContent();
      toast({
        title: 'File deleted',
        description: `${fileToDelete.filename} was removed from the knowledge base`,
      });
    } catch (error) {
      toast({
        title: 'Delete failed',
        description: error instanceof Error ? error.message : 'Failed to delete file',
        variant: 'destructive',
      });
    } finally {
      setDeletingFilename(null);
    }
  };

  const counts: Record<Tab, number> = {
    files: data.files.length,
    tables: data.tables.length,
    images: data.images.length,
  };

  return (
    <div className="flex flex-col h-full border-r bg-muted/20 overflow-hidden">
      <div className="px-3 py-2.5 border-b flex items-center justify-between shrink-0">
        <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          Knowledge
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={fetchContent}
          disabled={loading}
          title="Refresh"
        >
          <RefreshCw className={cn('h-3 w-3', loading && 'animate-spin')} />
        </Button>
      </div>

      <nav className="px-2 py-1.5 space-y-0.5 border-b shrink-0">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              'w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-left transition-colors',
              activeTab === id
                ? 'bg-black text-white'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            <Icon className="h-3.5 w-3.5 shrink-0" />
            <span>{label}</span>
            <span className="ml-auto text-[10px] opacity-60">{counts[id]}</span>
          </button>
        ))}
      </nav>

      <div className="flex-1 overflow-y-auto p-2">
        {activeTab === 'files' && (
          <FilesList
            files={data.files}
            deletingFilename={deletingFilename}
            onDeleteClick={setFileToDelete}
          />
        )}
        {activeTab === 'tables' && <TablesList tables={data.tables} />}
        {activeTab === 'images' && <ImagesList images={data.images} />}
      </div>

      <Dialog open={!!fileToDelete} onOpenChange={(open) => !open && setFileToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete document</DialogTitle>
            <DialogDescription>{fileToDelete?.filename}</DialogDescription>
          </DialogHeader>
          <DialogBody>
            <p className="text-sm text-muted-foreground">
              This removes all chunks, tables, images, and embeddings for this file from Supabase.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button
                variant="ghost"
                onClick={() => setFileToDelete(null)}
                disabled={!!deletingFilename}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={deleteFile}
                disabled={!!deletingFilename}
              >
                {deletingFilename ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Delete
              </Button>
            </div>
          </DialogBody>
        </DialogContent>
      </Dialog>
    </div>
  );
}
