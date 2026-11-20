import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  ArrowRight,
  BarChart3,
  Check,
  Database,
  FileSpreadsheet,
  KeyRound,
  Lock,
  MessageCircle,
  QrCode,
  ShieldCheck,
  Sparkles,
  Upload,
  Users,
  Zap,
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const PLANS = [
  {
    key: 'free',
    name: 'Free',
    priceInr: '₹0',
    priceUsd: '$0',
    description: 'Explore private AI document intelligence with your team',
    highlight: false,
    cta: 'Start Free',
    features: [
      '1 GB isolated vault storage',
      '12 AI queries / month',
      'Up to 2 team members · 1 API key',
      'CSV & TXT uploads',
    ],
  },
  {
    key: 'starter',
    name: 'Starter',
    priceInr: '₹3,000',
    priceUsd: '$49',
    description: 'Built for lean teams analyzing PDFs & financial sheets',
    highlight: false,
    cta: 'Upgrade via UPI',
    features: [
      '5 GB isolated vault storage',
      '500 AI queries / month',
      'Up to 5 team members',
      'PDF, Excel & CSV ingestion',
      'Interactive Recharts analytics',
    ],
  },
  {
    key: 'growth',
    name: 'Growth',
    priceInr: '₹7,000',
    priceUsd: '$99',
    description: 'For scaling B2B companies running daily AI workflows',
    highlight: true,
    cta: 'Upgrade via UPI',
    features: [
      '20 GB isolated vault storage',
      '2,500 AI queries / month',
      'Up to 15 team members',
      'Scoped Developer API Keys',
      'Full Team RBAC permissions',
    ],
  },
  {
    key: 'business',
    name: 'Business',
    priceInr: '₹15,000',
    priceUsd: '$199',
    description: 'Enterprise security controls, audit logs & unlimited seats',
    highlight: false,
    cta: 'Upgrade via UPI',
    features: [
      '100 GB isolated vault storage',
      '10,000 AI queries / month',
      'Unlimited team members',
      'Immutable Audit Log stream',
      'Priority enterprise support',
    ],
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen flex flex-col text-foreground">
      {/* Sticky Obsidian Glass Header Navbar */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#06080f]/80 backdrop-blur-xl">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2.5 font-bold text-base text-white">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 text-white shadow-lg shadow-violet-600/30">
              <Sparkles className="h-4 w-4" />
            </span>
            <span className="tracking-tight">InsightVault AI</span>
          </Link>

          <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-slate-400">
            <a href="#features" className="hover:text-white transition-colors">
              Features
            </a>
            <a href="#how-it-works" className="hover:text-white transition-colors">
              Architecture
            </a>
            <a href="#pricing" className="hover:text-white transition-colors">
              Pricing
            </a>
            <a href="#security" className="hover:text-white transition-colors">
              Security
            </a>
          </nav>

          <div className="flex items-center gap-2.5">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Sign In
              </Button>
            </Link>
            <Link href="/signup">
              <Button size="sm" className="gap-1.5">
                Get Started
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="relative overflow-hidden border-b border-white/10">
          <div className="container mx-auto px-4 py-20 lg:py-28">
            <div className="grid lg:grid-cols-2 gap-14 items-center">
              <div className="space-y-7">
                <div className="inline-flex items-center gap-2 rounded-full border border-violet-400/30 bg-violet-500/10 px-4 py-1.5 text-xs font-medium text-violet-200">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Enterprise Multi-Tenant AI Analyst · Gemini &amp; Self-Hosted vLLM Ready
                </div>

                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.08] text-white">
                  Turn Private Company Data Into{' '}
                  <span className="gradient-text">Boardroom-Ready Answers</span>
                </h1>

                <p className="text-base sm:text-lg text-slate-400 max-w-xl leading-relaxed">
                  Upload PDFs, Excel workbooks, and CSV exports into an encrypted multi-tenant vault. Ask in plain
                  English, render live interactive charts, manage RBAC teams, and upgrade instantly via zero-fee UPI.
                </p>

                <div className="flex flex-wrap gap-3 pt-1">
                  <Link href="/signup">
                    <Button size="lg" className="gap-2">
                      Launch Free Workspace
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </Link>
                  <Link href="/dashboard">
                    <Button variant="outline" size="lg">
                      Open Live Dashboard
                    </Button>
                  </Link>
                </div>

                <div className="flex flex-wrap items-center gap-6 pt-2 text-xs text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <ShieldCheck className="h-4 w-4 text-emerald-400" /> Strict Tenant Isolation
                  </span>
                  <span className="flex items-center gap-1.5">
                    <QrCode className="h-4 w-4 text-violet-400" /> Direct UPI QR Billing
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Zap className="h-4 w-4 text-cyan-400" /> Instant Cited Answers
                  </span>
                </div>
              </div>

              {/* Executive Glassmorphic Product Preview */}
              <div className="glass-panel rounded-2xl p-6 space-y-5 relative">
                <div className="flex items-center justify-between border-b border-white/10 pb-3.5">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                    <span className="ml-2 text-xs font-medium text-slate-400">
                      Apex Logistics · Encrypted Vault
                    </span>
                  </div>
                  <span className="rounded-full border border-emerald-400/30 bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
                    4 Docs Indexed
                  </span>
                </div>

                <div className="space-y-3">
                  <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3.5 text-sm">
                    <p className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Executive Query</p>
                    <p className="font-medium text-white">Which region generated the highest Q3 revenue?</p>
                  </div>
                  <div className="rounded-xl border border-violet-500/30 bg-violet-500/10 p-4 text-sm space-y-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-violet-200 flex items-center gap-1.5">
                        <Sparkles className="h-3.5 w-3.5 text-violet-300" /> Grounded AI Synthesis
                      </span>
                      <span className="rounded-md bg-black/40 px-2 py-0.5 text-[11px] font-mono text-cyan-300 border border-white/10">
                        [DOC_1] q3_sales_report.csv
                      </span>
                    </div>
                    <p className="text-slate-200 leading-relaxed">
                      <strong className="text-white">West</strong> led Q3 with{' '}
                      <strong className="text-emerald-300">$62,000</strong> in total revenue, outperforming South
                      ($49,500) and North ($33,500).
                    </p>
                  </div>
                </div>

                <div className="space-y-2.5 pt-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-400">Live Revenue Breakdown</span>
                    <span className="font-mono text-emerald-400">98% confidence</span>
                  </div>
                  <div className="space-y-2.5 text-xs">
                    {[
                      { label: 'West', value: '$62,000', width: '100%', color: 'from-violet-500 to-cyan-400' },
                      { label: 'South', value: '$49,500', width: '80%', color: 'from-indigo-500 to-violet-400' },
                      { label: 'North', value: '$33,500', width: '54%', color: 'from-slate-500 to-indigo-400' },
                    ].map((row) => (
                      <div key={row.label} className="flex items-center gap-3">
                        <span className="w-12 font-medium text-slate-300">{row.label}</span>
                        <div className="h-2 flex-1 rounded-full bg-white/10 overflow-hidden">
                          <div
                            className={`h-full rounded-full bg-gradient-to-r ${row.color}`}
                            style={{ width: row.width }}
                          />
                        </div>
                        <span className="w-16 text-right font-mono text-slate-200">{row.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Bento Features Grid */}
        <section id="features" className="container mx-auto px-4 py-24">
          <div className="text-center max-w-2xl mx-auto mb-16 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-widest text-violet-400">Platform Capabilities</p>
            <h2 className="text-3xl sm:text-4xl font-bold text-white">
              Everything Modern B2B Teams Need in One Vault
            </h2>
            <p className="text-slate-400">
              Engineered end-to-end for finance, operations, and leadership teams who demand speed and zero data leakage.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              {
                icon: FileSpreadsheet,
                title: 'PDF, Excel & CSV Vault',
                desc: 'Upload multi-page PDFs, Excel workbooks (.xlsx/.xls), CSVs, and policy docs with automatic chunking, SHA-256 verification, and embeddings.',
              },
              {
                icon: MessageCircle,
                title: 'Grounded AI Q&A',
                desc: 'Ask plain-English questions and receive concise answers grounded strictly in your tenant files with [DOC_N] citations.',
              },
              {
                icon: BarChart3,
                title: 'Interactive Executive Charts',
                desc: 'Turn any uploaded CSV or Excel sheet into interactive Bar, Line, and Pie charts with metric switching in one click.',
              },
              {
                icon: Users,
                title: 'Team Invites & RBAC',
                desc: 'Invite teammates with Owner, Admin, Member, or Viewer permissions and manage access directly from your dashboard.',
              },
              {
                icon: KeyRound,
                title: 'Scoped Developer API Keys',
                desc: 'Generate hashed API keys with expiration dates and instant revocation to query your company vault programmatically.',
              },
              {
                icon: QrCode,
                title: 'Zero-Fee UPI QR Billing',
                desc: 'Upgrade plans instantly using direct UPI QR & UPI ID payments with anti-replay UTR verification and automated invoices.',
              },
            ].map((feat) => (
              <Card key={feat.title} className="hover:border-violet-500/40 transition-colors">
                <CardHeader>
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/15 border border-violet-400/20 text-violet-300 mb-3">
                    <feat.icon className="h-5 w-5" />
                  </span>
                  <CardTitle>{feat.title}</CardTitle>
                  <CardDescription className="pt-1 leading-relaxed">{feat.desc}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </section>

        {/* How It Works / Architecture */}
        <section id="how-it-works" className="border-y border-white/10 bg-white/[0.02] py-24">
          <div className="container mx-auto px-4">
            <div className="text-center max-w-2xl mx-auto mb-16 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400">How It Works</p>
              <h2 className="text-3xl sm:text-4xl font-bold text-white">From Raw Files to Insights in 3 Steps</h2>
            </div>

            <div className="grid md:grid-cols-3 gap-8">
              {[
                {
                  step: '01',
                  icon: Upload,
                  title: 'Upload & Verify',
                  desc: 'Drop PDFs, Excel sheets, or CSV exports. Files are sanitized, SHA-256 hashed, and stored inside your isolated tenant path.',
                },
                {
                  step: '02',
                  icon: Database,
                  title: 'Parse, Chunk & Embed',
                  desc: 'Tables and pages are parsed into structured chunks and indexed for hybrid vector + keyword retrieval.',
                },
                {
                  step: '03',
                  icon: BarChart3,
                  title: 'Query, Chart & Audit',
                  desc: 'Ask questions in plain English, visualize numeric columns, and track every action in your immutable audit log.',
                },
              ].map((item) => (
                <div key={item.step} className="glass-panel rounded-2xl p-6 space-y-3.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono font-bold text-violet-300">STEP {item.step}</span>
                    <item.icon className="h-5 w-5 text-cyan-300" />
                  </div>
                  <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Pricing Section */}
        <section id="pricing" className="container mx-auto px-4 py-24">
          <div className="text-center max-w-2xl mx-auto mb-16 space-y-3">
            <div className="inline-flex items-center gap-1.5 rounded-full border border-violet-400/30 bg-violet-500/10 px-3.5 py-1 text-xs font-medium text-violet-200">
              <QrCode className="h-3.5 w-3.5" />
              Direct UPI QR &amp; UPI ID Checkout · 0% Gateway Fees
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold text-white">Transparent B2B Pricing</h2>
            <p className="text-slate-400">
              Start free and upgrade anytime directly inside your dashboard with instant UTR activation.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            {PLANS.map((plan) => (
              <Card
                key={plan.key}
                className={
                  plan.highlight
                    ? 'border-violet-500/60 bg-gradient-to-b from-violet-950/50 to-[#0c1222]/90 shadow-2xl shadow-violet-900/25 relative flex flex-col'
                    : 'flex flex-col'
                }
              >
                {plan.highlight && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-violet-500 to-cyan-500 px-3.5 py-0.5 text-[11px] font-semibold text-white shadow-md">
                    Most Popular
                  </span>
                )}
                <CardHeader>
                  <CardTitle className="text-xl">{plan.name}</CardTitle>
                  <div className="pt-3">
                    <span className="text-3xl font-bold text-white">{plan.priceInr}</span>
                    <span className="text-sm text-slate-400"> / month</span>
                    <p className="text-xs text-slate-500 mt-0.5">({plan.priceUsd} USD equivalent)</p>
                  </div>
                  <CardDescription className="pt-2">{plan.description}</CardDescription>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col justify-between space-y-6">
                  <ul className="space-y-2.5 text-sm text-slate-300">
                    {plan.features.map((feat) => (
                      <li key={feat} className="flex items-start gap-2">
                        <Check className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                        <span>{feat}</span>
                      </li>
                    ))}
                  </ul>
                  <Link href={plan.key === 'free' ? '/signup' : `/dashboard?tab=billing&plan=${plan.key}`}>
                    <Button variant={plan.highlight ? 'default' : 'outline'} className="w-full">
                      {plan.cta}
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        {/* Enterprise Security Architecture Section */}
        <section id="security" className="border-t border-white/10 bg-white/[0.02] py-20">
          <div className="container mx-auto px-4">
            <div className="glass-panel rounded-2xl p-8 lg:p-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8">
              <div className="space-y-4 max-w-2xl">
                <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">
                  <Lock className="h-4 w-4" /> Defense-in-Depth Security
                </div>
                <h3 className="text-2xl sm:text-3xl font-bold text-white">
                  Built From Day One for Strict Multi-Tenant Isolation
                </h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Every API call is enforced by tenant middleware, JWT rotation with refresh-token blacklisting on
                  logout, path-traversal storage guards, hard quota caps, duplicate-UTR replay protection, and
                  immutable audit logs.
                </p>
                <div className="flex flex-wrap gap-2 pt-1 text-xs">
                  {[
                    'JWT Token Blacklisting',
                    'Path-Traversal Guard',
                    'RBAC Permissions',
                    'UTR Anti-Replay',
                    'Immutable Audit Trail',
                    'CSP & Security Headers',
                  ].map((badge) => (
                    <span
                      key={badge}
                      className="rounded-full border border-emerald-400/25 bg-emerald-500/10 px-3 py-1 text-emerald-300"
                    >
                      {badge}
                    </span>
                  ))}
                </div>
              </div>
              <Link href="/signup">
                <Button size="lg" className="shrink-0 gap-2">
                  Create Secure Workspace
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-white/10 bg-[#05070d]">
        <div className="container mx-auto px-4 py-12">
          <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-8">
            <div className="space-y-3">
              <div className="flex items-center gap-2 font-bold text-white">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-cyan-500 text-white">
                  <Sparkles className="h-3.5 w-3.5" />
                </span>
                <span>InsightVault AI</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Private AI document &amp; data analyst built for security-first B2B teams.
              </p>
            </div>

            <div className="space-y-2 text-sm">
              <h4 className="font-semibold text-white">Product</h4>
              <ul className="space-y-1.5 text-slate-400 text-xs">
                <li><a href="#features" className="hover:text-white">Features</a></li>
                <li><a href="#how-it-works" className="hover:text-white">Architecture</a></li>
                <li><a href="#pricing" className="hover:text-white">Pricing &amp; UPI Plans</a></li>
                <li><Link href="/dashboard" className="hover:text-white">Workspace Dashboard</Link></li>
              </ul>
            </div>

            <div className="space-y-2 text-sm">
              <h4 className="font-semibold text-white">Account</h4>
              <ul className="space-y-1.5 text-slate-400 text-xs">
                <li><Link href="/login" className="hover:text-white">Sign In</Link></li>
                <li><Link href="/signup" className="hover:text-white">Create Workspace</Link></li>
                <li>
                  <a href={`${API_BASE_URL}/api/schema/swagger/`} target="_blank" rel="noreferrer" className="hover:text-white">
                    OpenAPI Docs (Swagger)
                  </a>
                </li>
              </ul>
            </div>

            <div className="space-y-2 text-sm">
              <h4 className="font-semibold text-white">Security &amp; Ops</h4>
              <ul className="space-y-1.5 text-slate-400 text-xs">
                <li><a href="#security" className="hover:text-white">Security Architecture</a></li>
                <li><a href="#pricing" className="hover:text-white">Direct UPI Payments</a></li>
                <li>
                  <a href={`${API_BASE_URL}/health/ready/`} target="_blank" rel="noreferrer" className="hover:text-white">
                    Live System Status
                  </a>
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-10 border-t border-white/10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-500">
            <p>© {new Date().getFullYear()} InsightVault AI. All rights reserved.</p>
            <p>Multi-Tenant B2B Micro-SaaS · End-to-End Secured</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
