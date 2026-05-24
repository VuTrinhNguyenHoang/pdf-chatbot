'use client';

import { useState, useEffect, useCallback } from 'react';
import { FileText, Table2, Image, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type { ContentEntry, ContentResponse, FileEntry } from '@/app/api/content/route';

type Tab = 'files' | 'tables' | 'images';

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'files', label: 'Files', icon: FileText },
  { id: 'tables', label: 'Tables', icon: Table2 },
  { id: 'images', label: 'Images', icon: Image },
];

// ── File list ──────────────────────────────────────────────────────────────

function FilesList({ files }: { files: FileEntry[] }) {
  if (!files.length) {
    return <Empty text="No files ingested yet" />;
  }
  return (
    <div className="space-y-1">
      {files.map((f) => (
        <div key={f.filename} className="px-2 py-1.5 rounded-md hover:bg-muted cursor-default">
          <p className="text-xs font-medium truncate" title={f.filename}>{f.filename}</p>
          <p className="text-[10px] text-muted-foreground">
            {f.chunks} chunks · {f.tables} tables · {f.images} images
          </p>
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
            <p className="text-[10px] text-muted-foreground">p.{img.page ?? '?'}</p>
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
            <p className="text-sm leading-relaxed text-muted-foreground">
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
}

export function KnowledgeSidebar({ refreshTrigger }: KnowledgeSidebarProps) {
  const [activeTab, setActiveTab] = useState<Tab>('files');
  const [data, setData] = useState<ContentResponse>({ files: [], tables: [], images: [] });
  const [loading, setLoading] = useState(false);

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
        {activeTab === 'files' && <FilesList files={data.files} />}
        {activeTab === 'tables' && <TablesList tables={data.tables} />}
        {activeTab === 'images' && <ImagesList images={data.images} />}
      </div>
    </div>
  );
}
