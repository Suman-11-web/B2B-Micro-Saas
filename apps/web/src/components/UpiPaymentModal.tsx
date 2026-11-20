'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api';
import { Check, Copy, QrCode, ShieldCheck, Smartphone, X } from 'lucide-react';

export interface PlanOption {
  key: string;
  name: string;
  price_monthly_inr: number;
  price_monthly_usd: number;
  description?: string;
}

interface UpiPaymentModalProps {
  plan: PlanOption | null;
  onClose: () => void;
  onSuccess: (message: string) => void;
}

const DEFAULT_UPI_ID = process.env.NEXT_PUBLIC_UPI_ID || 'your-upi-id@upi';
const MERCHANT_NAME = process.env.NEXT_PUBLIC_UPI_MERCHANT_NAME || 'InsightVault AI';

export function UpiPaymentModal({ plan, onClose, onSuccess }: UpiPaymentModalProps) {
  const [utrNumber, setUtrNumber] = useState('');
  const [payerUpiId, setPayerUpiId] = useState('');
  const [copied, setCopied] = useState(false);
  const [qrMissing, setQrMissing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!plan) return null;

  const amount = plan.price_monthly_inr;
  const upiUri = `upi://pay?pa=${encodeURIComponent(DEFAULT_UPI_ID)}&pn=${encodeURIComponent(
    MERCHANT_NAME
  )}&am=${amount}&cu=INR&tn=${encodeURIComponent(`${MERCHANT_NAME} ${plan.name} Plan`)}`;

  async function handleCopyUpi() {
    try {
      await navigator.clipboard.writeText(DEFAULT_UPI_ID);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!plan) return;
    setError('');
    setSubmitting(true);

    try {
      const res = await apiClient.upiUpgrade({
        plan_key: plan.key,
        utr_number: utrNumber.trim(),
        payer_upi_id: payerUpiId.trim(),
      });
      onSuccess(res.data.message || `Upgraded to ${plan.name} successfully!`);
      onClose();
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { message?: string; detail?: string } } };
      setError(
        axiosErr.response?.data?.message ||
          axiosErr.response?.data?.detail ||
          'Could not verify UPI upgrade. Please check your UTR number and try again.'
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md">
      <div className="glass-panel w-full max-w-md rounded-2xl p-6 space-y-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/20 text-violet-300 border border-violet-400/30">
                <QrCode className="h-4 w-4" />
              </span>
              UPI Instant Upgrade — {plan.name}
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              Total due:{' '}
              <span className="font-semibold text-white">
                ₹{amount.toLocaleString('en-IN')} / month
              </span>
            </p>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex flex-col items-center rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
          {!qrMissing ? (
            <div className="rounded-xl bg-white p-2.5 shadow-lg shadow-violet-900/20">
              <img
                src="/upi-qr.png"
                onError={() => setQrMissing(true)}
                alt={`UPI QR Code for ${MERCHANT_NAME}`}
                className="h-44 w-44 object-contain"
              />
            </div>
          ) : (
            <div className="flex h-44 w-44 flex-col items-center justify-center rounded-xl border border-dashed border-violet-400/40 bg-violet-500/10 p-4 text-center text-slate-300">
              <QrCode className="h-14 w-14 text-violet-300 mb-2" />
              <span className="text-xs font-medium text-white">Drop your QR at</span>
              <span className="text-[11px] font-mono text-violet-300">public/upi-qr.png</span>
            </div>
          )}

          <p className="text-xs text-slate-400 text-center">
            Scan with Google Pay, PhonePe, Paytm, or BHIM UPI
          </p>

          <div className="flex w-full items-center justify-between gap-2 rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm">
            <span className="font-mono text-xs text-slate-200 truncate">{DEFAULT_UPI_ID}</span>
            <Button type="button" variant="outline" size="sm" onClick={handleCopyUpi} className="shrink-0 gap-1.5">
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copied' : 'Copy UPI ID'}
            </Button>
          </div>

          <a
            href={upiUri}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-violet-400/30 bg-violet-500/15 px-3 py-2 text-xs font-medium text-violet-200 hover:bg-violet-500/25 transition-colors"
          >
            <Smartphone className="h-3.5 w-3.5" />
            Open UPI App on Mobile
          </a>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          <div className="space-y-1">
            <label htmlFor="utrNumber" className="text-xs font-medium text-slate-300">
              UPI Transaction ID / UTR Number *
            </label>
            <Input
              id="utrNumber"
              placeholder="e.g. 432198765432"
              value={utrNumber}
              onChange={(e) => setUtrNumber(e.target.value)}
              required={amount > 0}
              minLength={amount > 0 ? 6 : 0}
            />
          </div>

          <div className="space-y-1">
            <label htmlFor="payerUpiId" className="text-xs font-medium text-slate-300">
              Your UPI ID (optional)
            </label>
            <Input
              id="payerUpiId"
              placeholder="yourname@okaxis"
              value={payerUpiId}
              onChange={(e) => setPayerUpiId(e.target.value)}
            />
          </div>

          <p className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
            Protected against duplicate UTR replay · Instant invoice generated
          </p>

          <div className="flex gap-2 pt-1">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" disabled={submitting}>
              {submitting ? 'Verifying...' : 'Verify & Activate'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
