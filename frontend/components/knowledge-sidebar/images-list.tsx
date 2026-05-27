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

export function ImagesList({ images }: { images: ContentEntry[] }) {
  const [selected, setSelected] = useState<ContentEntry | null>(null);

  if (!images.length) return <EmptyState text="No images extracted" />;

  return (
    <>
      <div className="space-y-1">
        {images.map((image) => (
          <button
            key={image.id}
            onClick={() => setSelected(image)}
            className="w-full text-left px-2 py-1.5 rounded-md hover:bg-muted transition-colors group"
          >
            <p className="text-xs font-medium truncate group-hover:text-foreground">
              {image.title || image.filename}
            </p>
            <p className="text-[10px] text-muted-foreground">
              p.{image.page ?? '?'}
              {image.imageStatus && image.imageStatus !== 'extracted'
                ? ' · no preview'
                : ''}
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
