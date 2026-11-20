'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api';
import { Check, ShieldCheck, Sparkles } from 'lucide-react';

function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function getPasswordStrength(pw: string): { score: number; label: string; color: string } {
  let score = 0;
  if (pw.length >= 8) score += 1;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score += 1;
  if (/\d/.test(pw)) score += 1;
  if (/[^A-Za-z0-9]/.test(pw) || pw.length >= 12) score += 1;

  if (score <= 1) return { score, label: 'Weak', color: 'bg-red-500' };
  if (score === 2) return { score, label: 'Fair', color: 'bg-amber-400' };
  if (score === 3) return { score, label: 'Strong', color: 'bg-cyan-400' };
  return { score, label: 'Enterprise Strong', color: 'bg-emerald-400' };
}

export default function SignupPage() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [companySlug, setCompanySlug] = useState('');
  const [slugTouched, setSlugTouched] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const strength = getPasswordStrength(password);

  function handleCompanyNameChange(value: string) {
    setCompanyName(value);
    if (!slugTouched) {
      setCompanySlug(slugify(value));
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await apiClient.register({
        name,
        email,
        password,
        company_name: companyName,
        company_slug: companySlug || slugify(companyName),
      });

      const { access, refresh, company, user } = res.data;
      localStorage.setItem('auth_tokens', JSON.stringify({ access, refresh }));
      if (company?.id) {
        localStorage.setItem('tenant_id', company.id);
      }
      localStorage.setItem('user', JSON.stringify(user));
      localStorage.setItem('company', JSON.stringify(company));

      router.push('/dashboard');
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { message?: string; detail?: string } } };
      setError(
        axiosErr.response?.data?.message ||
          axiosErr.response?.data?.detail ||
          'Registration failed. Please check your details and try again.'
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <Link href="/" className="mb-8 flex items-center gap-2.5 font-bold text-lg text-white">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 text-white shadow-lg shadow-violet-600/30">
          <Sparkles className="h-4 w-4" />
        </span>
        <span>InsightVault AI</span>
      </Link>

      <Card className="w-full max-w-md glass-panel">
        <CardHeader className="space-y-1 text-center">
          <CardTitle className="text-2xl font-bold">Create your private vault</CardTitle>
          <CardDescription>Spin up an isolated B2B AI workspace in seconds</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-300">
                {error}
              </div>
            )}

            <div className="space-y-1.5">
              <label htmlFor="name" className="text-xs font-medium text-slate-300">
                Full Name
              </label>
              <Input
                id="name"
                placeholder="Jane Doe"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="email" className="text-xs font-medium text-slate-300">
                Work Email
              </label>
              <Input
                id="email"
                type="email"
                placeholder="jane@acme.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-xs font-medium text-slate-300">
                Password
              </label>
              <Input
                id="password"
                type="password"
                placeholder="Minimum 8 chars (letters + numbers)"
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              {password.length > 0 && (
                <div className="space-y-1 pt-1">
                  <div className="grid grid-cols-4 gap-1.5">
                    {[1, 2, 3, 4].map((level) => (
                      <div
                        key={level}
                        className={`h-1 rounded-full ${
                          strength.score >= level ? strength.color : 'bg-white/10'
                        }`}
                      />
                    ))}
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Strength: <span className="text-slate-200 font-medium">{strength.label}</span>
                  </p>
                </div>
              )}
            </div>

            <div className="grid sm:grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label htmlFor="companyName" className="text-xs font-medium text-slate-300">
                  Company Name
                </label>
                <Input
                  id="companyName"
                  placeholder="Acme Corp"
                  value={companyName}
                  onChange={(e) => handleCompanyNameChange(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="companySlug" className="text-xs font-medium text-slate-300">
                  Workspace Slug
                </label>
                <Input
                  id="companySlug"
                  placeholder="acme-corp"
                  value={companySlug}
                  onChange={(e) => {
                    setSlugTouched(true);
                    setCompanySlug(slugify(e.target.value));
                  }}
                  required
                />
              </div>
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Provisioning Workspace...' : 'Create Free Workspace'}
            </Button>
          </form>

          <div className="mt-5 flex flex-wrap items-center justify-center gap-3 text-[11px] text-slate-400">
            <span className="flex items-center gap-1">
              <Check className="h-3.5 w-3.5 text-emerald-400" /> Free tier included
            </span>
            <span className="flex items-center gap-1">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> Encrypted tenant isolation
            </span>
          </div>

          <p className="mt-5 text-center text-xs text-slate-400">
            Already have a workspace?{' '}
            <Link href="/login" className="font-medium text-violet-300 hover:text-violet-200 underline underline-offset-4">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
