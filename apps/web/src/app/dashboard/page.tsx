'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { UpiPaymentModal, type PlanOption } from '@/components/UpiPaymentModal';
import { apiClient } from '@/lib/api';
import {
  Activity,
  BarChart3,
  Check,
  Copy,
  CreditCard,
  FileSpreadsheet,
  FileText,
  KeyRound,
  Lock,
  LogOut,
  MessageCircle,
  QrCode,
  ShieldCheck,
  Sparkles,
  Trash2,
  Upload,
  UserPlus,
  Users,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

type TabKey = 'qa' | 'documents' | 'charts' | 'team' | 'billing' | 'apikeys' | 'security';
type ChartType = 'bar' | 'line' | 'pie';

interface CompanyInfo {
  id: string;
  name: string;
  slug: string;
  status: string;
  plan?: { key?: string; name: string } | null;
}

interface DocumentItem {
  id: string;
  filename: string;
  mime_type: string;
  status: string;
  file_size: number;
  page_count?: number;
  sheet_names?: string[];
  error_message?: string | null;
  created_at: string;
}

interface QueryItem {
  id: string;
  question: string;
  status: string;
  error_message?: string | null;
  result?: {
    answer_text?: string;
    summary?: string;
    confidence?: number;
    model?: string;
  } | null;
  created_at: string;
}

interface MembershipItem {
  id: string;
  role: string;
  status: string;
  user: { id: string; email: string; name: string };
  invited_at: string;
  joined_at?: string | null;
}

interface ApiKeyItem {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  is_expired: boolean;
  expires_at?: string | null;
  last_used_at?: string | null;
  created_at: string;
}

interface AuditLogItem {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  user_email?: string | null;
  ip_address?: string | null;
  created_at: string;
}

interface ChartDataset {
  document_id: string;
  filename: string;
  label_key: string;
  numeric_keys: string[];
  rows: Record<string, string | number>[];
}

interface BillingOverview {
  subscription?: {
    status: string;
    current_period_end: string;
    days_remaining: number;
  } | null;
  plan?: {
    key: string;
    name: string;
    price_monthly_inr: number;
    price_monthly_usd: number;
  } | null;
  available_plans?: (PlanOption & {
    storage_limit_bytes: number;
    query_limit_monthly: number;
    user_limit: number;
    features: string[];
  })[];
  invoices?: {
    id: string;
    provider_invoice_id: string;
    status: string;
    amount_inr: number;
    currency: string;
    paid_at?: string | null;
    created_at: string;
  }[];
  live_usage?: {
    queries_used: number;
    query_limit: number;
    storage_used_bytes: number;
    storage_limit_bytes: number;
    users_count: number;
    user_limit: number;
  };
}

const CHART_COLORS = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899'];

export default function DashboardPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [activeTab, setActiveTab] = useState<TabKey>('qa');
  const [company, setCompany] = useState<CompanyInfo | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [queries, setQueries] = useState<QueryItem[]>([]);
  const [memberships, setMemberships] = useState<MembershipItem[]>([]);
  const [billing, setBilling] = useState<BillingOverview | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKeyItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);

  // Q&A & Upload state
  const [question, setQuestion] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submittingQuery, setSubmittingQuery] = useState(false);

  // Charts state
  const [selectedChartDocId, setSelectedChartDocId] = useState<string>('');
  const [chartDataset, setChartDataset] = useState<ChartDataset | null>(null);
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [selectedMetric, setSelectedMetric] = useState<string>('');
  const [loadingChart, setLoadingChart] = useState(false);

  // Team invite state
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [inviting, setInviting] = useState(false);

  // API Key creation state
  const [newKeyName, setNewKeyName] = useState('');
  const [creatingKey, setCreatingKey] = useState(false);
  const [newlyCreatedRawKey, setNewlyCreatedRawKey] = useState('');
  const [copiedKey, setCopiedKey] = useState(false);

  // UPI Modal state
  const [selectedPlanForUpi, setSelectedPlanForUpi] = useState<PlanOption | null>(null);

  // Global feedback
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const tabularDocs = documents.filter(
    (d) =>
      d.status === 'ready' &&
      (d.mime_type === 'text/csv' ||
        d.mime_type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
        d.mime_type === 'application/vnd.ms-excel')
  );

  async function loadAllData() {
    try {
      const [compRes, docsRes, queriesRes] = await Promise.all([
        apiClient.getCurrentCompany(),
        apiClient.listDocuments(),
        apiClient.listQueries(),
      ]);

      setCompany(compRes.data);
      setDocuments(docsRes.data.results || docsRes.data || []);
      setQueries(queriesRes.data.results || queriesRes.data || []);

      const [teamRes, billRes, keysRes, auditRes] = await Promise.allSettled([
        apiClient.listMemberships(),
        apiClient.getBillingOverview(),
        apiClient.listApiKeys(),
        apiClient.listAuditLogs(),
      ]);

      if (teamRes.status === 'fulfilled') setMemberships(teamRes.value.data.results || teamRes.value.data || []);
      if (billRes.status === 'fulfilled') setBilling(billRes.value.data);
      if (keysRes.status === 'fulfilled') setApiKeys(keysRes.value.data.results || keysRes.value.data || []);
      if (auditRes.status === 'fulfilled') setAuditLogs(auditRes.value.data.results || auditRes.value.data || []);
    } catch {
      router.push('/login');
    } finally {
      setLoading(false);
    }
  }

  async function loadChartForDocument(docId: string) {
    if (!docId) return;
    setLoadingChart(true);
    setError('');
    try {
      const res = await apiClient.getDocumentChartData(docId);
      const data: ChartDataset = res.data;
      setChartDataset(data);
      setSelectedChartDocId(docId);
      if (data.numeric_keys.length > 0) setSelectedMetric(data.numeric_keys[0]);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { message?: string } } };
      setError(axiosErr.response?.data?.message || 'Could not load chart data for this document.');
    } finally {
      setLoadingChart(false);
    }
  }

  useEffect(() => {
    const tokens = localStorage.getItem('auth_tokens');
    if (!tokens) {
      router.push('/login');
      return;
    }

    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab') as TabKey | null;
      if (tab && ['qa', 'documents', 'charts', 'team', 'billing', 'apikeys', 'security'].includes(tab)) {
        setActiveTab(tab);
      }
    }

    loadAllData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (activeTab === 'charts' && !selectedChartDocId && tabularDocs.length > 0) {
      loadChartForDocument(tabularDocs[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, documents.length]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please choose a PDF, Excel, CSV, or TXT file first.');
      return;
    }
    setUploading(true);
    setError('');
    setSuccess('');

    try {
      const res = await apiClient.uploadDocument(selectedFile);
      setSuccess(`Uploaded "${res.data.filename}" — Status: ${res.data.status.toUpperCase()}.`);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadAllData();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { message?: string; detail?: string } } };
      setError(axiosErr.response?.data?.message || axiosErr.response?.data?.detail || 'File upload failed.');
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteDocument(id: string) {
    setError('');
    try {
      await apiClient.deleteDocument(id);
      setSuccess('Document deleted.');
      if (selectedChartDocId === id) {
        setSelectedChartDocId('');
        setChartDataset(null);
      }
      await loadAllData();
    } catch {
      setError('Failed to delete document.');
    }
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setSubmittingQuery(true);
    setError('');
    setSuccess('');

    try {
      await apiClient.createQuery({ question: question.trim(), source_filter: 'all' });
      setQuestion('');
      await loadAllData();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { message?: string; detail?: string } } };
      setError(axiosErr.response?.data?.message || axiosErr.response?.data?.detail || 'Query failed.');
    } finally {
      setSubmittingQuery(false);
    }
  }

  async function handleInviteMember(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setError('');
    setSuccess('');

    try {
      await apiClient.inviteMember({ user_email: inviteEmail.trim(), role: inviteRole });
      setSuccess(`Invited ${inviteEmail.trim()} as ${inviteRole}.`);
      setInviteEmail('');
      await loadAllData();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { message?: string; detail?: string } } };
      setError(axiosErr.response?.data?.message || axiosErr.response?.data?.detail || 'Invite failed.');
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(memberId: string, role: string) {
    setError('');
    try {
      await apiClient.changeMemberRole(memberId, role);
      setSuccess('Member role updated.');
      await loadAllData();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { message?: string } } };
      setError(axiosErr.response?.data?.message || 'Failed to update role.');
    }
  }

  async function handleActivateMember(memberId: string) {
    setError('');
    try {
      await apiClient.activateMember(memberId);
      setSuccess('Member activated.');
      await loadAllData();
    } catch {
      setError('Failed to activate member.');
    }
  }

  async function handleRemoveMember(memberId: string) {
    setError('');
    try {
      await apiClient.removeMember(memberId);
      setSuccess('Member removed.');
      await loadAllData();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { message?: string } } };
      setError(axiosErr.response?.data?.message || 'Failed to remove member.');
    }
  }

  async function handleCreateApiKey(e: React.FormEvent) {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setCreatingKey(true);
    setError('');
    setSuccess('');

    try {
      const res = await apiClient.createApiKey({
        name: newKeyName.trim(),
        scopes: ['read', 'write'],
        expires_in_days: 90,
      });
      setNewlyCreatedRawKey(res.data.raw_key || '');
      setNewKeyName('');
      setSuccess('API key generated. Copy it now — it will only be shown once.');
      await loadAllData();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { message?: string; detail?: string } } };
      setError(axiosErr.response?.data?.message || axiosErr.response?.data?.detail || 'Could not create API key.');
    } finally {
      setCreatingKey(false);
    }
  }

  async function handleRevokeApiKey(id: string) {
    setError('');
    try {
      await apiClient.revokeApiKey(id);
      setSuccess('API key revoked immediately.');
      await loadAllData();
    } catch {
      setError('Failed to revoke API key.');
    }
  }

  async function handleLogout() {
    try {
      const tokens = localStorage.getItem('auth_tokens');
      if (tokens) {
        const { refresh } = JSON.parse(tokens);
        await apiClient.logout(refresh);
      }
    } catch {
      // Proceed with local cleanup even if token already expired
    } finally {
      localStorage.removeItem('auth_tokens');
      localStorage.removeItem('tenant_id');
      localStorage.removeItem('user');
      localStorage.removeItem('company');
      router.push('/login');
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-slate-400 text-sm">Decrypting workspace session...</p>
      </div>
    );
  }

  const tabs: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { key: 'qa', label: 'AI Analyst', icon: MessageCircle },
    { key: 'documents', label: `Documents (${documents.length})`, icon: FileText },
    { key: 'charts', label: 'Charts', icon: BarChart3 },
    { key: 'team', label: `Team (${memberships.length})`, icon: Users },
    { key: 'billing', label: 'Billing & UPI', icon: CreditCard },
    { key: 'apikeys', label: 'API Keys', icon: KeyRound },
    { key: 'security', label: 'Security & Audit', icon: ShieldCheck },
  ];

  const usage = billing?.live_usage;
  const queryPct =
    usage && usage.query_limit > 0 ? Math.min(100, Math.round((usage.queries_used / usage.query_limit) * 100)) : 0;
  const storagePct =
    usage && usage.storage_limit_bytes > 0
      ? Math.min(100, Math.round((usage.storage_used_bytes / usage.storage_limit_bytes) * 100))
      : 0;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Executive Workspace Header */}
      <header className="sticky top-0 z-30 border-b border-white/10 bg-[#06080f]/85 backdrop-blur-xl">
        <div className="container mx-auto flex h-16 items-center justify-between px-4 gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Link href="/" className="flex items-center gap-2 font-bold text-white shrink-0">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 text-white shadow-lg shadow-violet-600/30">
                <Sparkles className="h-4 w-4" />
              </span>
              <span className="hidden sm:inline">InsightVault AI</span>
            </Link>
            <span className="text-slate-600">/</span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white truncate">{company?.name || 'Workspace'}</p>
              <p className="text-[11px] text-slate-400">
                {billing?.plan?.name || company?.plan?.name || 'Free'} Plan · {company?.status || 'trial'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden md:inline-flex items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-300">
              <Lock className="h-3 w-3" /> Tenant Isolated
            </span>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setActiveTab('billing')}>
              <QrCode className="h-3.5 w-3.5 text-violet-300" />
              Upgrade
            </Button>
            <Button variant="ghost" size="sm" onClick={handleLogout} className="gap-1.5 text-slate-300">
              <LogOut className="h-3.5 w-3.5" />
              Sign Out
            </Button>
          </div>
        </div>

        {/* Navigation Pill Bar */}
        <div className="container mx-auto px-4 flex gap-1 overflow-x-auto pb-0">
          {tabs.map((t) => {
            const Icon = t.icon;
            const isActive = activeTab === t.key;
            return (
              <button
                key={t.key}
                type="button"
                onClick={() => setActiveTab(t.key)}
                className={`flex items-center gap-2 border-b-2 px-3.5 py-2.5 text-xs sm:text-sm font-medium whitespace-nowrap transition-colors ${
                  isActive
                    ? 'border-violet-400 text-white'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? 'text-violet-300' : ''}`} />
                {t.label}
              </button>
            );
          })}
        </div>
      </header>

      <main className="container mx-auto flex-1 px-4 py-6 space-y-6">
        {/* Executive KPI Strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="glass-panel rounded-xl p-4">
            <p className="text-xs text-slate-400">Indexed Documents</p>
            <p className="text-2xl font-bold text-white mt-1">{documents.length}</p>
            <p className="text-[11px] text-cyan-300 mt-0.5">{tabularDocs.length} chart-ready tables</p>
          </div>
          <div className="glass-panel rounded-xl p-4">
            <p className="text-xs text-slate-400">Monthly AI Queries</p>
            <p className="text-2xl font-bold text-white mt-1">
              {usage?.queries_used ?? queries.length}
              <span className="text-sm font-normal text-slate-500"> / {usage?.query_limit ?? 50}</span>
            </p>
            <div className="h-1.5 rounded-full bg-white/10 mt-2 overflow-hidden">
              <div className="h-full bg-gradient-to-r from-violet-500 to-cyan-400" style={{ width: `${queryPct}%` }} />
            </div>
          </div>
          <div className="glass-panel rounded-xl p-4">
            <p className="text-xs text-slate-400">Active Team Seats</p>
            <p className="text-2xl font-bold text-white mt-1">
              {memberships.length || 1}
              <span className="text-sm font-normal text-slate-500">
                {' '}
                / {usage?.user_limit && usage.user_limit > 0 ? usage.user_limit : '∞'}
              </span>
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">RBAC enforced</p>
          </div>
          <div className="glass-panel rounded-xl p-4">
            <p className="text-xs text-slate-400">Security Posture</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">Protected</p>
            <p className="text-[11px] text-slate-400 mt-0.5">{auditLogs.length} audit events logged</p>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3.5 text-sm text-red-300">{error}</div>
        )}
        {success && (
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5 text-sm text-emerald-300">
            {success}
          </div>
        )}

        {/* TAB 1: AI ANALYST */}
        {activeTab === 'qa' && (
          <div className="grid lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MessageCircle className="h-5 w-5 text-violet-400" />
                  Ask AI Analyst
                </CardTitle>
                <CardDescription>
                  Query uploaded PDFs, Excel workbooks, CSV exports, and handbooks with grounded citations
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <form onSubmit={handleAsk} className="flex gap-2">
                  <Input
                    placeholder="e.g., What is the total revenue across all months?"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                  />
                  <Button type="submit" disabled={submittingQuery}>
                    {submittingQuery ? 'Analyzing...' : 'Ask'}
                  </Button>
                </form>

                <div className="space-y-3 pt-2">
                  {queries.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-white/15 p-8 text-center text-sm text-slate-400">
                      No queries yet. Upload a PDF, Excel, CSV, or TXT file on the right and ask your first question.
                    </div>
                  ) : (
                    queries.map((q) => (
                      <div key={q.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <span className="font-semibold text-white">{q.question}</span>
                          <span
                            className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase shrink-0 ${
                              q.status === 'completed'
                                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                                : q.status === 'failed'
                                ? 'bg-red-500/15 text-red-300 border border-red-500/30'
                                : 'bg-white/10 text-slate-300'
                            }`}
                          >
                            {q.status}
                          </span>
                        </div>
                        {q.result?.answer_text && (
                          <p className="text-slate-300 whitespace-pre-wrap leading-relaxed">{q.result.answer_text}</p>
                        )}
                        {q.result?.model && (
                          <p className="text-[11px] text-slate-500 font-mono">
                            model: {q.result.model}
                            {typeof q.result.confidence === 'number' &&
                              ` · confidence: ${Math.round(q.result.confidence * 100)}%`}
                          </p>
                        )}
                        {q.error_message && <p className="text-xs text-red-400">{q.error_message}</p>}
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Upload className="h-4 w-4 text-violet-400" />
                  Quick Document Upload
                </CardTitle>
                <CardDescription>PDF, Excel (.xlsx/.xls), CSV, TXT</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <form
                  onSubmit={handleUpload}
                  className="space-y-3 rounded-xl border border-dashed border-white/15 p-3.5 bg-white/[0.02]"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.xlsx,.xls,.csv,.txt"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-violet-600 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white cursor-pointer"
                  />
                  <Button type="submit" size="sm" disabled={uploading || !selectedFile} className="w-full">
                    {uploading ? 'Processing...' : 'Upload & Index'}
                  </Button>
                </form>

                <div className="space-y-2">
                  <p className="text-xs font-medium text-slate-400">Indexed Files ({documents.length})</p>
                  {documents.slice(0, 5).map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.02] p-2.5 text-xs"
                    >
                      <span className="truncate font-medium text-slate-200">{doc.filename}</span>
                      <span className="uppercase text-[10px] text-emerald-400 font-semibold ml-2">{doc.status}</span>
                    </div>
                  ))}
                  {documents.length > 5 && (
                    <Button variant="ghost" size="sm" className="w-full text-xs" onClick={() => setActiveTab('documents')}>
                      View all {documents.length} documents
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* TAB 2: DOCUMENTS */}
        {activeTab === 'documents' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileSpreadsheet className="h-5 w-5 text-violet-400" />
                Encrypted Document Vault
              </CardTitle>
              <CardDescription>
                Upload PDF, Excel (.xlsx/.xls), CSV, or TXT files. Tabular files can be charted instantly.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <form
                onSubmit={handleUpload}
                className="flex flex-col sm:flex-row gap-3 rounded-xl border border-dashed border-white/15 p-4 bg-white/[0.02]"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.xlsx,.xls,.csv,.txt"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="block flex-1 text-sm text-slate-300 file:mr-4 file:rounded-lg file:border-0 file:bg-violet-600 file:px-3.5 file:py-2 file:text-sm file:font-medium file:text-white cursor-pointer"
                />
                <Button type="submit" disabled={uploading || !selectedFile}>
                  {uploading ? 'Uploading & Parsing...' : 'Upload File'}
                </Button>
              </form>

              <div className="space-y-2.5">
                {documents.length === 0 ? (
                  <p className="text-sm text-slate-400 text-center py-8">
                    No documents uploaded yet. Upload a PDF, Excel, CSV, or TXT file above.
                  </p>
                ) : (
                  documents.map((doc) => {
                    const isTabular =
                      doc.mime_type === 'text/csv' ||
                      doc.mime_type.includes('spreadsheet') ||
                      doc.mime_type.includes('excel');
                    return (
                      <div
                        key={doc.id}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3.5 text-sm"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <FileText className="h-5 w-5 text-violet-400 shrink-0" />
                          <div className="min-w-0">
                            <p className="font-medium text-white truncate">{doc.filename}</p>
                            <p className="text-xs text-slate-400">
                              {(doc.file_size / 1024).toFixed(1)} KB · {doc.status.toUpperCase()}
                              {doc.page_count ? ` · ${doc.page_count} page(s)` : ''}
                              {doc.sheet_names && doc.sheet_names.length > 0
                                ? ` · Sheets: ${doc.sheet_names.join(', ')}`
                                : ''}
                            </p>
                            {doc.error_message && <p className="text-xs text-red-400">{doc.error_message}</p>}
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {isTabular && doc.status === 'ready' && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="gap-1.5"
                              onClick={() => {
                                setActiveTab('charts');
                                loadChartForDocument(doc.id);
                              }}
                            >
                              <BarChart3 className="h-3.5 w-3.5 text-cyan-300" />
                              Visualize
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteDocument(doc.id)}
                            title="Delete document"
                          >
                            <Trash2 className="h-4 w-4 text-red-400" />
                          </Button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* TAB 3: CHARTS */}
        {activeTab === 'charts' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-cyan-400" />
                Interactive Executive Charts
              </CardTitle>
              <CardDescription>
                Live Bar, Line, and Pie visualizations extracted directly from your uploaded CSV &amp; Excel files
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {tabularDocs.length === 0 ? (
                <div className="rounded-xl border border-dashed border-white/15 p-10 text-center space-y-3">
                  <p className="text-sm text-slate-400">
                    Upload a CSV or Excel (.xlsx) file to generate interactive charts automatically.
                  </p>
                  <Button variant="outline" onClick={() => setActiveTab('documents')}>
                    Go to Documents
                  </Button>
                </div>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-3">
                    <select
                      value={selectedChartDocId}
                      onChange={(e) => loadChartForDocument(e.target.value)}
                      className="h-10 rounded-lg border border-white/15 bg-[#0c1222] px-3 text-sm text-white"
                    >
                      {tabularDocs.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.filename}
                        </option>
                      ))}
                    </select>

                    {chartDataset && chartDataset.numeric_keys.length > 0 && (
                      <select
                        value={selectedMetric}
                        onChange={(e) => setSelectedMetric(e.target.value)}
                        className="h-10 rounded-lg border border-white/15 bg-[#0c1222] px-3 text-sm text-white"
                      >
                        {chartDataset.numeric_keys.map((k) => (
                          <option key={k} value={k}>
                            Metric: {k}
                          </option>
                        ))}
                      </select>
                    )}

                    <div className="flex rounded-lg border border-white/15 overflow-hidden">
                      {(['bar', 'line', 'pie'] as ChartType[]).map((type) => (
                        <button
                          key={type}
                          type="button"
                          onClick={() => setChartType(type)}
                          className={`px-3.5 py-2 text-xs font-semibold uppercase ${
                            chartType === type
                              ? 'bg-violet-600 text-white'
                              : 'bg-white/[0.03] text-slate-400 hover:text-white'
                          }`}
                        >
                          {type}
                        </button>
                      ))}
                    </div>
                  </div>

                  {loadingChart ? (
                    <div className="h-80 flex items-center justify-center text-sm text-slate-400">
                      Rendering visualization...
                    </div>
                  ) : chartDataset && chartDataset.rows.length > 0 && selectedMetric ? (
                    <div className="h-96 w-full rounded-xl border border-white/10 bg-[#080c17] p-4">
                      <ResponsiveContainer width="100%" height="100%">
                        {chartType === 'bar' ? (
                          <BarChart data={chartDataset.rows}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
                            <XAxis dataKey={chartDataset.label_key} stroke="#94a3b8" fontSize={12} />
                            <YAxis stroke="#94a3b8" fontSize={12} />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: '#0f172a',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '0.75rem',
                                color: '#f8fafc',
                              }}
                            />
                            <Legend />
                            <Bar dataKey={selectedMetric} fill="#8b5cf6" radius={[6, 6, 0, 0]} />
                          </BarChart>
                        ) : chartType === 'line' ? (
                          <LineChart data={chartDataset.rows}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
                            <XAxis dataKey={chartDataset.label_key} stroke="#94a3b8" fontSize={12} />
                            <YAxis stroke="#94a3b8" fontSize={12} />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: '#0f172a',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '0.75rem',
                                color: '#f8fafc',
                              }}
                            />
                            <Legend />
                            <Line type="monotone" dataKey={selectedMetric} stroke="#06b6d4" strokeWidth={2.5} />
                          </LineChart>
                        ) : (
                          <PieChart>
                            <Pie
                              data={chartDataset.rows}
                              dataKey={selectedMetric}
                              nameKey={chartDataset.label_key}
                              cx="50%"
                              cy="50%"
                              outerRadius={125}
                              label
                            >
                              {chartDataset.rows.map((_, idx) => (
                                <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip
                              contentStyle={{
                                backgroundColor: '#0f172a',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '0.75rem',
                                color: '#f8fafc',
                              }}
                            />
                            <Legend />
                          </PieChart>
                        )}
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="text-sm text-slate-400">No numeric columns found in this file.</p>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        )}

        {/* TAB 4: TEAM & RBAC */}
        {activeTab === 'team' && (
          <div className="grid lg:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <UserPlus className="h-4 w-4 text-violet-400" />
                  Invite Team Member
                </CardTitle>
                <CardDescription>Assign role-based permissions per tenant</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleInviteMember} className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-300">Work Email</label>
                    <Input
                      type="email"
                      placeholder="teammate@company.com"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-300">Role</label>
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                      className="h-10 w-full rounded-lg border border-white/15 bg-[#0c1222] px-3 text-sm text-white"
                    >
                      <option value="admin">Admin (Manage users, billing &amp; docs)</option>
                      <option value="member">Member (Upload docs &amp; ask AI)</option>
                      <option value="viewer">Viewer (Read-only access)</option>
                    </select>
                  </div>
                  <Button type="submit" className="w-full" disabled={inviting}>
                    {inviting ? 'Sending Invite...' : 'Send Invite'}
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Users className="h-4 w-4 text-violet-400" />
                  Workspace Members ({memberships.length})
                </CardTitle>
                <CardDescription>Manage roles and membership status</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {memberships.map((m) => (
                  <div
                    key={m.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3.5 text-sm"
                  >
                    <div>
                      <p className="font-medium text-white">{m.user.name || m.user.email}</p>
                      <p className="text-xs text-slate-400">
                        {m.user.email} · <span className="uppercase font-semibold text-cyan-300">{m.status}</span>
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      {m.role === 'owner' ? (
                        <span className="rounded-full bg-violet-500/20 border border-violet-400/30 px-2.5 py-0.5 text-xs font-semibold text-violet-200 uppercase">
                          Owner
                        </span>
                      ) : (
                        <>
                          <select
                            value={m.role}
                            onChange={(e) => handleRoleChange(m.id, e.target.value)}
                            className="h-8 rounded-lg border border-white/15 bg-[#0c1222] px-2 text-xs text-white"
                          >
                            <option value="admin">Admin</option>
                            <option value="member">Member</option>
                            <option value="viewer">Viewer</option>
                          </select>
                          {m.status === 'invited' && (
                            <Button size="sm" variant="outline" onClick={() => handleActivateMember(m.id)}>
                              Activate
                            </Button>
                          )}
                          <Button size="sm" variant="ghost" onClick={() => handleRemoveMember(m.id)}>
                            <Trash2 className="h-3.5 w-3.5 text-red-400" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        )}

        {/* TAB 5: BILLING & UPI */}
        {activeTab === 'billing' && (
          <div className="space-y-6">
            <div className="grid md:grid-cols-3 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Active Plan</CardDescription>
                  <CardTitle className="text-2xl">{billing?.plan?.name || 'Free'}</CardTitle>
                </CardHeader>
                <CardContent className="text-xs text-slate-400">
                  ₹{(billing?.plan?.price_monthly_inr || 0).toLocaleString('en-IN')} / month ·{' '}
                  {billing?.subscription?.status || 'active'}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Monthly AI Queries</CardDescription>
                  <CardTitle className="text-2xl">
                    {usage?.queries_used ?? 0} / {usage?.query_limit ?? 50}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-violet-500 to-cyan-400" style={{ width: `${queryPct}%` }} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Storage Used</CardDescription>
                  <CardTitle className="text-2xl">
                    {((usage?.storage_used_bytes ?? 0) / (1024 * 1024)).toFixed(2)} MB
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-2 rounded-full bg-white/10 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400"
                      style={{ width: `${Math.max(storagePct, 3)}%` }}
                    />
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <QrCode className="h-5 w-5 text-violet-400" />
                  Subscription Plans — Direct UPI QR / UPI ID Checkout
                </CardTitle>
                <CardDescription>
                  Zero payment gateway fees. Scan the UPI QR, enter your UTR reference, and activate instantly.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {(billing?.available_plans || []).map((plan) => {
                    const isCurrent = billing?.plan?.key === plan.key;
                    return (
                      <div
                        key={plan.key}
                        className={`rounded-xl border p-4 flex flex-col justify-between space-y-4 ${
                          isCurrent
                            ? 'border-violet-500/60 bg-violet-500/10'
                            : 'border-white/10 bg-white/[0.02]'
                        }`}
                      >
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <h3 className="font-bold text-white">{plan.name}</h3>
                            {isCurrent && (
                              <span className="rounded-full bg-violet-500 px-2 py-0.5 text-[10px] font-semibold text-white">
                                Current
                              </span>
                            )}
                          </div>
                          <p className="text-2xl font-bold text-white">
                            ₹{plan.price_monthly_inr.toLocaleString('en-IN')}
                            <span className="text-xs font-normal text-slate-400">/mo</span>
                          </p>
                          <ul className="space-y-1 text-xs text-slate-400 pt-2">
                            <li className="flex items-center gap-1.5">
                              <Check className="h-3.5 w-3.5 text-emerald-400" />
                              {Math.round(plan.storage_limit_bytes / (1024 * 1024 * 1024))} GB storage
                            </li>
                            <li className="flex items-center gap-1.5">
                              <Check className="h-3.5 w-3.5 text-emerald-400" />
                              {plan.query_limit_monthly.toLocaleString()} queries/mo
                            </li>
                            <li className="flex items-center gap-1.5">
                              <Check className="h-3.5 w-3.5 text-emerald-400" />
                              {plan.user_limit < 0 ? 'Unlimited seats' : `${plan.user_limit} team seats`}
                            </li>
                          </ul>
                        </div>

                        <Button
                          size="sm"
                          variant={isCurrent ? 'outline' : 'default'}
                          disabled={isCurrent}
                          onClick={() => setSelectedPlanForUpi(plan)}
                          className="w-full"
                        >
                          {isCurrent ? 'Active Plan' : plan.price_monthly_inr === 0 ? 'Switch to Free' : 'Pay with UPI'}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">UPI Invoices &amp; Payment History</CardTitle>
              </CardHeader>
              <CardContent>
                {!billing?.invoices || billing.invoices.length === 0 ? (
                  <p className="text-sm text-slate-400">No invoices yet.</p>
                ) : (
                  <div className="space-y-2">
                    {billing.invoices.map((inv) => (
                      <div
                        key={inv.id}
                        className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.02] p-3 text-sm"
                      >
                        <div>
                          <p className="font-medium text-white font-mono text-xs">
                            UTR / Ref: {inv.provider_invoice_id || inv.id.slice(0, 8)}
                          </p>
                          <p className="text-xs text-slate-400">
                            {new Date(inv.paid_at || inv.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="font-semibold text-white">₹{inv.amount_inr.toLocaleString('en-IN')}</p>
                          <span className="text-[11px] uppercase font-semibold text-emerald-400">{inv.status}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* TAB 6: DEVELOPER API KEYS */}
        {activeTab === 'apikeys' && (
          <div className="grid lg:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <KeyRound className="h-4 w-4 text-violet-400" />
                  Generate Scoped API Key
                </CardTitle>
                <CardDescription>Hashed at rest with 90-day expiry and instant revocation</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <form onSubmit={handleCreateApiKey} className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-slate-300">Key Label</label>
                    <Input
                      placeholder="e.g. Production CRM Integration"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                      required
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={creatingKey}>
                    {creatingKey ? 'Generating...' : 'Generate API Key'}
                  </Button>
                </form>

                {newlyCreatedRawKey && (
                  <div className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 p-3 space-y-2">
                    <p className="text-xs font-semibold text-emerald-300">Copy your secret key (shown once):</p>
                    <p className="font-mono text-xs text-white break-all bg-black/40 p-2 rounded">
                      {newlyCreatedRawKey}
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="w-full gap-1.5"
                      onClick={async () => {
                        await navigator.clipboard.writeText(newlyCreatedRawKey);
                        setCopiedKey(true);
                        setTimeout(() => setCopiedKey(false), 2000);
                      }}
                    >
                      {copiedKey ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                      {copiedKey ? 'Copied!' : 'Copy Secret Key'}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Active &amp; Revoked API Keys ({apiKeys.length})</CardTitle>
                <CardDescription>Send via <code className="text-cyan-300">X-API-Key</code> header</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2.5">
                {apiKeys.length === 0 ? (
                  <p className="text-sm text-slate-400">No API keys created yet.</p>
                ) : (
                  apiKeys.map((k) => (
                    <div
                      key={k.id}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/[0.03] p-3.5 text-sm"
                    >
                      <div>
                        <p className="font-medium text-white">{k.name}</p>
                        <p className="text-xs font-mono text-slate-400">
                          {k.key_prefix}•••••••• · {k.is_active ? 'ACTIVE' : 'REVOKED'}
                        </p>
                      </div>
                      {k.is_active && (
                        <Button size="sm" variant="destructive" onClick={() => handleRevokeApiKey(k.id)}>
                          Revoke
                        </Button>
                      )}
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* TAB 7: SECURITY & AUDIT LOGS */}
        {activeTab === 'security' && (
          <div className="space-y-6">
            <div className="grid md:grid-cols-3 gap-4">
              {[
                { label: 'Tenant Isolation', value: 'Strict Row-Level', note: 'Middleware + DRF BelongsToTenant' },
                { label: 'Session Security', value: 'JWT + Blacklist', note: 'Tokens revoked server-side on logout' },
                { label: 'Upload & Billing Guard', value: 'Active', note: 'Path-traversal + UTR anti-replay' },
              ].map((item) => (
                <Card key={item.label}>
                  <CardHeader className="pb-2">
                    <CardDescription>{item.label}</CardDescription>
                    <CardTitle className="text-xl text-emerald-400 flex items-center gap-2">
                      <ShieldCheck className="h-5 w-5" />
                      {item.value}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-xs text-slate-400">{item.note}</CardContent>
                </Card>
              ))}
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity className="h-4 w-4 text-cyan-400" />
                  Immutable Security Audit Trail ({auditLogs.length})
                </CardTitle>
                <CardDescription>Every tenant-scoped mutation is logged with actor, resource, and timestamp</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {auditLogs.length === 0 ? (
                  <p className="text-sm text-slate-400">No audit events recorded yet.</p>
                ) : (
                  auditLogs.slice(0, 25).map((log) => (
                    <div
                      key={log.id}
                      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-white/[0.02] px-3.5 py-2.5 text-xs"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="rounded bg-violet-500/20 border border-violet-400/30 px-2 py-0.5 font-mono uppercase text-[10px] text-violet-200">
                          {log.action}
                        </span>
                        <span className="font-medium text-white">{log.resource_type}</span>
                        {log.user_email && <span className="text-slate-400">by {log.user_email}</span>}
                      </div>
                      <span className="text-slate-500 font-mono">
                        {log.ip_address ? `${log.ip_address} · ` : ''}
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </main>

      <UpiPaymentModal
        plan={selectedPlanForUpi}
        onClose={() => setSelectedPlanForUpi(null)}
        onSuccess={async (msg) => {
          setSuccess(msg);
          await loadAllData();
        }}
      />
    </div>
  );
}
