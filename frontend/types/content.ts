export interface ContentEntry {
  id: string;
  content: string;
  filename: string;
  title?: string;
  page?: number;
  imageUrl?: string;
  imageMimeType?: string;
  imageStatus?: string;
}

export interface FileEntry {
  filename: string;
  chunks: number;
  tables: number;
  images: number;
}

export interface ContentResponse {
  files: FileEntry[];
  tables: ContentEntry[];
  images: ContentEntry[];
}

export interface DeleteContentResponse {
  deleted: number;
}
