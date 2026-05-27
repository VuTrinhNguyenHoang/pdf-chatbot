import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogBody,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import type { FileEntry } from '@/types/content';

interface DeleteDocumentDialogProps {
  file: FileEntry | null;
  deletingFilename: string | null;
  onClose: () => void;
  onDelete: () => void;
}

export function DeleteDocumentDialog({
  file,
  deletingFilename,
  onClose,
  onDelete,
}: DeleteDocumentDialogProps) {
  return (
    <Dialog open={!!file} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete document</DialogTitle>
          <DialogDescription>{file?.filename}</DialogDescription>
        </DialogHeader>
        <DialogBody>
          <p className="text-sm text-muted-foreground">
            This removes all chunks, tables, images, and embeddings for this file from Supabase.
          </p>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose} disabled={!!deletingFilename}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={onDelete}
              disabled={!!deletingFilename}
            >
              {deletingFilename ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Delete
            </Button>
          </div>
        </DialogBody>
      </DialogContent>
    </Dialog>
  );
}
