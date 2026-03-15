/**
 * Dataset API client.
 */

import { apiClient } from './client';

export interface ColumnSchema {
  key: string;
  type: 'text' | 'number' | 'percent' | 'currency' | 'date';
  unit?: string;
  format?: Record<string, unknown>;
  nullable?: boolean;
}

export interface DatasetResponse {
  dataset_id: string;
  company_id: string;
  name: string;
  description?: string;
  schema_json: { columns: ColumnSchema[] };
  rows_json: (string | number | null)[][];
  meta_json: Record<string, unknown>;
  current_revision: number;
  created_by?: string;
  updated_by?: string;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface DatasetListItem {
  dataset_id: string;
  company_id: string;
  name: string;
  description?: string;
  current_revision: number;
  row_count: number;
  column_count: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetCreate {
  name: string;
  description?: string;
  schema_json: { columns: ColumnSchema[] };
  rows_json: (string | number | null)[][];
  meta_json?: Record<string, unknown>;
}

export interface DatasetUpdate {
  name?: string;
  description?: string;
  schema_json?: { columns: ColumnSchema[] };
  rows_json?: (string | number | null)[][];
  meta_json?: Record<string, unknown>;
}

export interface DatasetImportPreview {
  detected_columns: ColumnSchema[];
  preview_rows: (string | number | null)[][];
  total_rows: number;
  warnings: string[];
  errors: string[];
}

export interface DatasetRevisionResponse {
  revision_id: string;
  dataset_id: string;
  revision_number: number;
  schema_json: { columns: ColumnSchema[] };
  rows_json: (string | number | null)[][];
  meta_json: Record<string, unknown>;
  created_at_utc: string;
  created_by: string | null;
  reason: string | null;
}

// === API Functions ===

export async function listDatasets(params?: {
  skip?: number;
  limit?: number;
  include_deleted?: boolean;
}): Promise<{ items: DatasetListItem[]; total: number }> {
  const response = await apiClient.get<{ items: DatasetListItem[]; total: number }>(
    '/api/v1/datasets',
    { params }
  );
  return response.data;
}

export async function getDataset(datasetId: string): Promise<DatasetResponse> {
  const response = await apiClient.get<DatasetResponse>(`/api/v1/datasets/${datasetId}`);
  return response.data;
}

export async function getDatasetRevision(revisionId: string): Promise<DatasetRevisionResponse> {
  const response = await apiClient.get<DatasetRevisionResponse>(`/api/v1/datasets/revisions/${revisionId}`);
  return response.data;
}

export async function createDataset(data: DatasetCreate): Promise<DatasetResponse> {
  const response = await apiClient.post<DatasetResponse>('/api/v1/datasets', data);
  return response.data;
}

export async function updateDataset(
  datasetId: string,
  data: DatasetUpdate,
  createRevision?: boolean
): Promise<DatasetResponse> {
  const response = await apiClient.patch<DatasetResponse>(
    `/api/v1/datasets/${datasetId}`,
    data,
    { params: { create_revision: createRevision } }
  );
  return response.data;
}

export async function deleteDataset(datasetId: string, hard?: boolean): Promise<void> {
  await apiClient.delete(`/api/v1/datasets/${datasetId}`, {
    params: { hard_delete: hard },
  });
}

// === Import/Export ===

export async function importCSVPreview(file: File): Promise<DatasetImportPreview> {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await apiClient.post<DatasetImportPreview>(
    '/api/v1/datasets/import/csv/preview',
    formData
  );
  return response.data;
}

export async function importCSVConfirm(params: {
  file: File;
  name: string;
  description?: string;
  schema_json: { columns: ColumnSchema[] };
  skip_rows?: number;
  max_rows?: number;
}): Promise<DatasetResponse> {
  const formData = new FormData();
  formData.append('file', params.file);
  formData.append('name', params.name);
  if (params.description) formData.append('description', params.description);
  formData.append('schema_json', JSON.stringify(params.schema_json));
  if (params.skip_rows) formData.append('skip_rows', String(params.skip_rows));
  if (params.max_rows) formData.append('max_rows', String(params.max_rows));
  
  const response = await apiClient.post<DatasetResponse>(
    '/api/v1/datasets/import/csv/confirm',
    formData
  );
  return response.data;
}

export async function importXLSXPreview(params: {
  file: File;
  sheet_name?: string;
  skip_rows?: number;
}): Promise<DatasetImportPreview> {
  const formData = new FormData();
  formData.append('file', params.file);
  if (params.sheet_name) formData.append('sheet_name', params.sheet_name);
  if (params.skip_rows) formData.append('skip_rows', String(params.skip_rows));
  
  const response = await apiClient.post<DatasetImportPreview>(
    '/api/v1/datasets/import/xlsx/preview',
    formData
  );
  return response.data;
}

export async function importXLSXConfirm(params: {
  file: File;
  name: string;
  description?: string;
  schema_json: { columns: ColumnSchema[] };
  sheet_name?: string;
  skip_rows?: number;
  max_rows?: number;
}): Promise<DatasetResponse> {
  const formData = new FormData();
  formData.append('file', params.file);
  formData.append('name', params.name);
  if (params.description) formData.append('description', params.description);
  formData.append('schema_json', JSON.stringify(params.schema_json));
  if (params.sheet_name) formData.append('sheet_name', params.sheet_name);
  if (params.skip_rows) formData.append('skip_rows', String(params.skip_rows));
  if (params.max_rows) formData.append('max_rows', String(params.max_rows));
  
  const response = await apiClient.post<DatasetResponse>(
    '/api/v1/datasets/import/xlsx/confirm',
    formData
  );
  return response.data;
}

export async function exportDatasetCSV(datasetId: string, revisionId?: string): Promise<Blob> {
  const response = await apiClient.get<Blob>(`/api/v1/datasets/${datasetId}/export/csv`, {
    params: { revision_id: revisionId },
    responseType: 'blob',
  });
  return response.data;
}

export async function exportDatasetXLSX(
  datasetId: string,
  revisionId?: string,
  includeMetadata = true
): Promise<Blob> {
  const response = await apiClient.get<Blob>(`/api/v1/datasets/${datasetId}/export/xlsx`, {
    params: { revision_id: revisionId, include_metadata: includeMetadata },
    responseType: 'blob',
  });
  return response.data;
}

export async function exportDatasetJSON(
  datasetId: string,
  revisionId?: string,
  includeMetadata = true
): Promise<Blob> {
  const response = await apiClient.get<Blob>(`/api/v1/datasets/${datasetId}/export/json`, {
    params: { revision_id: revisionId, include_metadata: includeMetadata },
    responseType: 'blob',
  });
  return response.data;
}
