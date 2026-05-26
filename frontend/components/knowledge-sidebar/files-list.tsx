import { Loader2, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { FileEntry } from '@/types/content';
import { EmptyState } from './empty-state';

interface FilesListProps {
  files: FileEntry[];
  deletingFilename: string | null;
  onDeleteClick: (file: FileEntry) => void;
}

export function FilesList({
  files,
  deletingFilename,
  onDeleteClick,
}: FilesListProps) {
  if (!files.length) {
    return <EmptyState text="No files ingested yet" />;
  }

  return (
    <div className="space-y-1">
      {files.map((file) => (
        <div
          key={file.filename}
          className="group flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted"
        >
          <div className="min-w-0 flex-1 cursor-default">
            <p className="text-xs font-medium truncate" title={file.filename}>
              {file.filename}
            </p>
            <p className="text-[10px] text-muted-foreground">
              {file.chunks} chunks · {file.tables} tables · {file.images} images
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
            onClick={() => onDeleteClick(file)}
            disabled={deletingFilename === file.filename}
            title={`Delete ${file.filename}`}
          >
            {deletingFilename === file.filename ? (
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
