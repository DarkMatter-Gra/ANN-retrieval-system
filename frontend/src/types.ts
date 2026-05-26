export type Role =
  | "admin"
  | "dev"
  | "user"
  | "service"
  | "readonly"
  | "auditor";

export type UserInfo = {
  user_id: number;
  username: string;
  role: Role;
  quota?: { used: number; limit: number };
  menus?: string[];
  dashboard_route?: string;
};

export type DatasetItem = {
  dataset_id: number;
  dataset_name?: string;
  file_format?: string;
  cell_count?: number;
  gene_count?: number;
  qc_status?: string;
  preprocess_status?: string;
  feature_dim?: number;
  created_at?: string;
};

export type DatasetDetail = {
  dataset_info?: Record<string, unknown>;
  qc_report?: Record<string, unknown>;
  preprocess_status?: string;
};

export type DatasetLogs = {
  steps?: {
    step: string;
    status: string;
    duration_ms?: number;
    message?: string;
  }[];
  warnings?: string[];
  errors?: string[];
};

export type IndexItem = {
  index_id: number;
  index_name?: string;
  index_type?: string;
  metric_type?: string;
  version_no?: number;
  build_status?: string;
  publish_status?: string;
  recall_score?: number;
  memory_cost_mb?: number;
  is_loaded?: boolean;
  status?: string;
  recall?: number;
  memory_usage?: number;
};

export type SearchResult = {
  rank: number;
  cell_id: string;
  distance: number;
  score: number;
  cell_type?: string | null;
  organ?: string | null;
  sample_id?: string | null;
};

export type SearchResponse = {
  query_id?: string;
  results?: SearchResult[];
  latency_ms?: number;
  recall_estimate?: number;
};

export type TaskSnapshot = {
  task_id?: string;
  type?: string;
  progress?: number;
  status?: string;
  result_url?: string;
  error_message?: string;
  started_at?: string;
  finished_at?: string;
};

export type EmbeddingPoint = Record<string, unknown> & { cell_id: string };

export type EmbeddingResponse = {
  points?: EmbeddingPoint[];
  total?: number;
  legend?: string[];
  method?: string;
};
