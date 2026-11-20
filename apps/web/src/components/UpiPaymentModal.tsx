'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api';
import { Check, Copy, Lock, QrCode, RefreshCw, ShieldCheck, Smartphone, X } from 'lucide-react';

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
  const [merchantUpiId, setMerchantUpiId] = useState(DEFAULT_UPI_ID);
  const [qrDataUri, setQrDataUri] = useState('');
  const [upiUri, setUpiUri] = useState('');
  const [generatingQr, setGeneratingQr] = useState(false);

  const [utrNumber, setUtrNumber] = useState('');
  const [payerUpiId, setPayerUpiId] = useState('');
  const [copied, setCopied] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  async function buildQr(targetPlan: PlanOption, upi: string) {
    if (!upi.trim()) return;
    setGeneratingQr(true);
    setError('');
    try {
      const res = await apiClient.generateUpiQr({
        plan: targetPlan.key,
        upi_id: upi.trim(),
        merchant: MERCHANT_NAME,
      });
      setQrDataUri(res.data.qr_data_uri || '');
      setUpiUri(res.data.upi_uri || '');
    } catch {
      setError('Could not generate UPI QR code. Check your UPI ID and try again.');
    } finally {
      setGeneratingQr(false);
    }
  }

  useEffect(() => {
    if (plan && plan.price_monthly_inr > 0) {
      buildQr(plan, merchantUpiId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan?.key]);

  if (!plan) return null;

  const amount = plan.price_monthly_inr;

  async function handleCopyUpi() {
    try {
      await navigator.clipboard.writeText(merchantUpiId);
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md overflow-y-auto">
      <div className="glass-panel w-full max-w-md rounded-2xl p-6 space-y-4 my-auto">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/20 text-violet-300 border border-violet-400/30">
                <QrCode className="h-4 w-4" />
              </span>
              Dynamic UPI QR — {plan.name}
            </h2>
            <p className="text-xs text-slate-400 mt-1 flex items-center gap-1.5">
              <Lock className="h-3 w-3 text-emerald-400" />
              Fixed locked amount:{' '}
              <span className="font-semibold text-white">₹{amount.toLocaleString('en-IN')} / month</span>
            </p>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {amount > 0 && (
          <div className="flex flex-col items-center rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
            <div className="w-full flex gap-2">
              <Input
                value={merchantUpiId}
                onChange={(e) => setMerchantUpiId(e.target.value)}
                placeholder="Merchant UPI ID (e.g. name@okaxis)"
                className="h-8 text-xs font-mono"
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={generatingQr}
                onClick={() => buildQr(plan, merchantUpiId)}
                className="shrink-0 gap-1"
              >
                <RefreshCw className={`h-3 w-3 ${generatingQr ? 'animate-spin' : ''}`} />
                Generate
              </Button>
            </div>

            {qrDataUri ? (
              <div className="rounded-xl bg-white p-2.5 shadow-xl shadow-violet-900/30">
                <img
                  src={qrDataUri}
                  alt={`UPI QR Code for ₹${amount}`}
                  className="h-44 w-44 object-contain"
                />
              </div>
            ) : (
              <div className="flex h-44 w-44 items-center justify-center rounded-xl border border-dashed border-white/15 text-xs text-slate-400">
                {generatingQr ? 'Generating QR...' : 'Enter UPI ID & Generate'}
              </div>
            )}

            <p className="text-[11px] text-slate-400 text-center">
              Scan with GPay, PhonePe, Paytm, or BHIM — ₹{amount.toLocaleString('en-IN')} is pre-filled automatically
            </p>

            <div className="flex w-full items-center justify-between gap-2 rounded-lg border border-white/10 bg-black/30 px-3 py-1.5 text-xs">
              <span className="font-mono text-slate-200 truncate">{merchantUpiId}</span>
              <Button type="button" variant="outline" size="sm" onClick={handleCopyUpi} className="shrink-0 gap-1">
                {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                {copied ? 'Copied' : 'Copy'}
              </Button>
            </div>

            {upiUri && (
              <a
                href={upiUri}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-violet-400/30 bg-violet-500/15 px-3 py-2 text-xs font-medium text-violet-200 hover:bg-violet-500/25 transition-colors"
              >
                <Smartphone className="h-3.5 w-3.5" />
                Pay ₹{amount.toLocaleString('en-IN')} in UPI App
              </a>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 text-xs text-red-300">
              {error}
            </div>
          )}

          {amount > 0 && (
            <>
              <div className="space-y-1">
                <label htmlFor="utrNumber" className="text-xs font-medium text-slate-300">
                  UPI Transaction ID / UTR Number *
                </label>
                <Input
                  id="utrNumber"
                  placeholder="e.g. 432198765432"
                  value={utrNumber}
                  onChange={(e) => setUtrNumber(e.target.value)}
                  required
                  minLength={6}
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
            </>
          )}

          <p className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
            Real NPCI QR engine · Fixed plan amount · Anti-replay UTR protection
          </p>

          <div className="flex gap-2 pt-1">
            <Button type="button" variant="outline" className="flex-1" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" disabled={submitting}>
              {submitting ? 'Activating...' : amount > 0 ? 'Verify & Activate' : 'Confirm Plan'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
