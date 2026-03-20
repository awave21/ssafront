export interface ResponseTransform {
  mode: 'fields' | 'jmespath';
  fields?: Array<{source: string; target: string}>;
  arrays?: Array<{
    source: string;
    target: string;
    fields: Array<{source: string; target: string}>;
  }>;
  expression?: string;
}

export interface Tool {
  id?: string;
  name: string;
  description: string;
  endpoint: string;
  http_method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  execution_type: 'http_webhook' | 'internal';
  auth_type: 'none' | 'api_key' | 'oauth2' | 'service';
  credential_id?: string | null;
  input_schema: any;
  parameter_mapping: Record<string, 'path' | 'query' | 'body'> | null;
  response_transform: ResponseTransform | null;
  headers?: Record<string, string> | null;
  status?: 'active' | 'deprecated';
  webhook_scope?: 'tool' | 'function_only' | 'both';
  version?: number;
  created_at?: string;
  updated_at?: string;
  is_deleted?: boolean;
}

export interface ToolBinding {
  id: string;
  agent_id: string;
  tool_id: string;
  permission_scope: 'read' | 'write';
  timeout_ms?: number | null;
  allowed_domains?: string[] | null;
  credential_id?: string | null;
  tool?: Tool | null;
}

export interface ToolTestRequest {
  args: Record<string, any>;
  endpoint?: string;
  http_method?: string;
  parameter_mapping?: Record<string, string> | null;
  custom_headers?: Record<string, string>;
  auth_type?: string;
  credential_id?: string | null;
  response_transform?: ResponseTransform | null;
}

export interface ToolTestResponse {
  status_code: number;
  latency_ms: number;
  raw_body: any;
  transformed_body: any | null;
  raw_size_bytes: number;
  transformed_size_bytes: number | null;
  error: string | null;
  request_url: string;
  request_method: string;
}
