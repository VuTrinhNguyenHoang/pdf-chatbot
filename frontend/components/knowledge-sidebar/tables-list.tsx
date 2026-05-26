'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import type { ContentEntry } from '@/types/content';
import { EmptyState } from './empty-state';
import { MarkdownTable } from './markdown-table';

export function TablesList({ tables }: { tables: ContentEntry[] }) {
  const [selected, setSelected] = useState<ContentEntry | null>(null);

  if (!tables.length) return <EmptyState text="No tables extracted" />;

  return (
    <>
      <div className="space-y-1">
        {tables.map((table) => (
          <button
            key={table.id}
            onClick={() => setSelected(table)}
            className="w-full text-left px-2 py-1.5 rounded-md hover:bg-muted transition-colors group"
          >
            <p className="text-xs font-medium truncate group-hover:text-foreground">
              {table.title || table.filename}
            </p>
            <p className="text-[10px] text-muted-foreground">
              p.{table.page ?? '?'}
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
            <MarkdownTable content={selected?.content ?? ''} />
          </DialogBody>
        </DialogContent>
      </Dialog>
    </>
  );
}
