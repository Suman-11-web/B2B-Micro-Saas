/**
 * API client for B2B Micro-SaaS
 * Handles JWT authentication, automatic token refresh, token revocation on logout, and tenant scoping
 */

import axios, { AxiosError, AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

export const apiClient = {
  // Auth
  login: (data: { email: string; password: string; company_id?: string }) =>
    api.post('/api/v1/auth/login/', data),

  logout: (refresh?: string) => api.post('/api/v1/auth/logout/', refresh ? { refresh } : {}),

  register: (data: { email: string; name: string; password: string; company_name: string; company_slug: string }) =>
    api.post('/api/v1/auth/register/', data),

  // Companies
  getCurrentCompany: () => api.get('/api/v1/companies/current/'),

  updateCompany: (data: Record<string, unknown>) => api.patch('/api/v1/companies/update_current/', data),

  // Team / Memberships
  listMemberships: () => api.get('/api/v1/memberships/'),

  inviteMember: (data: { user_email: string; role: string }) => api.post('/api/v1/memberships/', data),

  changeMemberRole: (id: string, role: string) => api.patch(`/api/v1/memberships/${id}/change_role/`, { role }),

  activateMember: (id: string) => api.post(`/api/v1/memberships/${id}/activate/`),

  removeMember: (id: string) => api.post(`/api/v1/memberships/${id}/remove/`),

  // API Keys & Security Audit Logs
  listApiKeys: () => api.get('/api/v1/api-keys/'),

  createApiKey: (data: { name: string; scopes: string[]; expires_in_days?: number }) =>
    api.post('/api/v1/api-keys/', data),

  revokeApiKey: (id: string) => api.post(`/api/v1/api-keys/${id}/revoke/`),

  listAuditLogs: () => api.get('/api/v1/audit-logs/'),

  // Documents
  listDocuments: (params?: Record<string, unknown>) => api.get('/api/v1/documents/', { params }),

  getDocument: (id: string) => api.get(`/api/v1/documents/${id}/`),

  uploadDocument: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/v1/documents/upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  getDocumentChartData: (id: string) => api.get(`/api/v1/documents/${id}/chart-data/`),

  reprocessDocument: (id: string) => api.post(`/api/v1/documents/${id}/reprocess/`),

  deleteDocument: (id: string) => api.delete(`/api/v1/documents/${id}/`),

  getDocumentChunks: (id: string, params?: Record<string, unknown>) => api.get(`/api/v1/documents/${id}/chunks/`, { params }),

  // Queries
  createQuery: (data: Record<string, unknown>) => api.post('/api/v1/queries/', data),

  getQuery: (id: string) => api.get(`/api/v1/queries/${id}/`),

  listQueries: (params?: Record<string, unknown>) => api.get('/api/v1/queries/', { params }),

  // Plans & Billing
  listPlans: () => api.get('/api/v1/plans/'),

  getBillingOverview: () => api.get('/api/v1/billing/overview/'),

  generateUpiQr: (params: { plan: string; upi_id: string; merchant?: string }) =>
    api.get('/api/v1/billing/upi-qr/', { params }),

  upiUpgrade: (data: { plan_key: string; utr_number: string; payer_upi_id?: string }) =>
    api.post('/api/v1/billing/upi-upgrade/', data),

  listInvoices: () => api.get('/api/v1/invoices/'),

  getUsage: (params?: Record<string, unknown>) => api.get('/api/v1/usage-summaries/', { params }),

  getQuotaStatus: () => api.get('/api/v1/quota-checks/current/'),
};

export default api;
