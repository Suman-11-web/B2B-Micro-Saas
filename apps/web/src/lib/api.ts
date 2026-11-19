/**
 * API client for B2B Micro-SaaS
 * Handles authentication, retry logic, and request/response transformation
 */

import axios, { AxiosError, AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for auth token
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig): Promise<InternalAxiosRequestConfig> => {
    if (typeof window !== 'undefined') {
      const tokens = localStorage.getItem('auth_tokens');
      if (tokens) {
        try {
          const { access } = JSON.parse(tokens);
          if (access) {
            config.headers.Authorization = `Bearer ${access}`;
          }
        } catch {
          localStorage.removeItem('auth_tokens');
        }
      }

      const tenantId = localStorage.getItem('tenant_id');
      if (tenantId) {
        config.headers['X-Tenant-ID'] = tenantId;
      }
    }

    return config;
  },
  (error: AxiosError) => Promise.reject(error)
);

// Response interceptor for error handling and token refresh
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: AxiosError): Promise<AxiosResponse> => {
    const originalRequest = error.config as RetryableRequestConfig | undefined;

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;

      if (typeof window !== 'undefined') {
        const tokens = localStorage.getItem('auth_tokens');
        if (tokens) {
          try {
            const { refresh } = JSON.parse(tokens);
            if (refresh) {
              const response = await axios.post(`${API_URL}/api/v1/auth/refresh/`, {
                refresh,
              });

              const newTokens = response.data;
              localStorage.setItem('auth_tokens', JSON.stringify(newTokens));

              originalRequest.headers.Authorization = `Bearer ${newTokens.access}`;
              return api(originalRequest);
            }
          } catch {
            localStorage.removeItem('auth_tokens');
            window.location.href = '/login';
          }
        }
      }
    }

    if (error.response?.status === 429 && originalRequest) {
      const retryAfter = error.response.headers['retry-after'] || error.response.headers['Retry-After'];
      if (retryAfter) {
        await new Promise((resolve) => setTimeout(resolve, parseInt(String(retryAfter), 10) * 1000));
        return api(originalRequest);
      }
    }

    return Promise.reject(error);
  }
);

// API endpoints
export const apiClient = {
  // Auth
  login: (data: { email: string; password: string; company_id?: string }) =>
    api.post('/api/v1/auth/login/', data),

  logout: () => api.post('/api/v1/auth/logout/'),

  register: (data: { email: string; name: string; password: string; company_name: string; company_slug: string }) =>
    api.post('/api/v1/auth/register/', data),

  // Companies
  getCurrentCompany: () => api.get('/api/v1/companies/current/'),

  updateCompany: (data: Record<string, unknown>) => api.patch('/api/v1/companies/update_current/', data),

  // Documents
  listDocuments: (params?: Record<string, unknown>) => api.get('/api/v1/documents/', { params }),

  getDocument: (id: string) => api.get(`/api/v1/documents/${id}/`),

  initiateDocumentUpload: (data: Record<string, unknown>) => api.post('/api/v1/documents/', data),

  confirmDocumentUpload: (id: string) => api.post(`/api/v1/documents/${id}/confirm_upload/`),

  reprocessDocument: (id: string) => api.post(`/api/v1/documents/${id}/reprocess/`),

  deleteDocument: (id: string) => api.delete(`/api/v1/documents/${id}/`),

  getDocumentChunks: (id: string, params?: Record<string, unknown>) => api.get(`/api/v1/documents/${id}/chunks/`, { params }),

  // Queries
  createQuery: (data: Record<string, unknown>) => api.post('/api/v1/queries/', data),

  getQuery: (id: string) => api.get(`/api/v1/queries/${id}/`),

  listQueries: (params?: Record<string, unknown>) => api.get('/api/v1/queries/', { params }),

  // Billing
  getBillingOverview: () => api.get('/api/v1/billing/overview/'),

  getUsage: (params?: Record<string, unknown>) => api.get('/api/v1/usage-summaries/', { params }),

  getQuotaStatus: () => api.get('/api/v1/quota-checks/current/'),
};

export default api;
