import { AlertCircle, CheckCircle2, FileIcon, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export type FileUploadStatus = 'queued' | 'uploading' | 'ingesting' | 'done' | 'error';

interface FilePreviewProps {
  file: File;
  status?: FileUploadStatus;
  error?: string;
  disabled?: boolean;
  onRemove: () => void;
}

const STATUS_LABELS: Record<FileUploadStatus, string> = {
  queued: 'Queued',
  uploading: 'Uploading',
  ingesting: 'Ingesting',
  done: 'Ready',
  error: 'Failed',
};

function StatusIcon({ status }: { status: FileUploadStatus }) {
  if (status === 'done') return <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />;
  if (status === 'error') return <AlertCircle className="h-3.5 w-3.5 text-destructive" />;
  if (status === 'uploading' || status === 'ingesting') {
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-gray-500" />;
  }
  return null;
}

export function FilePreview({
  file,
  status = 'done',
  error,
  disabled,
  onRemove,
}: FilePreviewProps) {
  return (
    <div className="flex items-center gap-2 bg-white rounded-lg p-2 shadow-sm">
      <div
        className={cn(
          'w-10 h-10 rounded-lg flex items-center justify-center',
          status === 'error' ? 'bg-destructive' : 'bg-pink-500',
        )}
      >
        <FileIcon className="w-6 h-6 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate text-gray-700">{file.name}</p>
        <p className="flex items-center gap-1 text-xs text-gray-500" title={error}>
          <StatusIcon status={status} />
          <span>{error || STATUS_LABELS[status]}</span>
        </p>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8 text-gray-500 hover:text-gray-900"
        onClick={onRemove}
        disabled={disabled}
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}
