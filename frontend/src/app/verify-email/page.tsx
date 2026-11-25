/**
 * Verify Email Page
 * Verify email using token from email link
 */

'use client';

import React, { useState, Suspense, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { MainLayout } from '@/components/layout/MainLayout';
import { cn } from '@/lib/utils';
import {
  MailIcon,
  AlertCircleIcon,
  CheckCircleIcon,
  ArrowLeftIcon,
} from '@/components/ui/icons';

function VerifyEmailPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(true);
  const [token] = useState(searchParams.get('token') || '');
  const [resending, setResending] = useState(false);

  const verifyMutation = useMutation({
    mutationFn: async (data: { token: string }) => {
      const response = await apiClient.post('/auth/verify-email', data);
      return response;
    },
    onSuccess: () => {
      setVerifying(false);
      setSuccess('Email verified successfully! You can now sign in to your account.');
      setError(null);
    },
    onError: (err: any) => {
      setVerifying(false);
      const message = err.response?.data?.detail || 'Failed to verify email. The link may have expired.';
      setError(message);
    },
  });

  const resendMutation = useMutation({
    mutationFn: async (data: { email: string }) => {
      const response = await apiClient.post('/auth/resend-verification', data);
      return response;
    },
    onSuccess: () => {
      setResending(false);
      setSuccess('A new verification email has been sent. Please check your inbox.');
      setError(null);
    },
    onError: (err: any) => {
      setResending(false);
      const message = err.response?.data?.detail || 'Failed to send verification email. Please try again.';
      setError(message);
    },
  });

  // Auto-verify on page load if token exists
  useEffect(() => {
    if (token) {
      verifyMutation.mutate({ token });
    } else {
      setVerifying(false);
      setError('No verification token provided. Please check your email for the verification link.');
    }
  }, [token]);

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setResending(true);

    // We need the email from the token or user input
    // Since we don't have the email here, we'll need to extract it from the token
    // For now, we'll show an error asking them to use the forgot password flow
    // In a real app, you might decode the token to get the email
    const email = searchParams.get('email');
    if (email) {
      resendMutation.mutate({ email });
    } else {
      setResending(false);
      setError('Unable to resend verification. Please use the "Resend verification" option in settings or contact support.');
    }
  };

  if (verifying) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <Link href="/" className="inline-flex items-center gap-2 mb-6">
              <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
                <CheckCircleIcon className="w-6 h-6 text-primary-foreground" />
              </div>
              <span className="text-2xl font-bold text-foreground">StateFlow</span>
            </Link>
            <h1 className="text-3xl font-bold text-foreground">Verify Email</h1>
            <p className="text-muted-foreground mt-2">Verifying your email address...</p>
          </div>
          <div className="bg-card border border-border rounded-xl p-6 shadow-sm text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent mx-auto mb-4" />
            <p className="text-muted-foreground">Please wait while we verify your email</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
              <CheckCircleIcon className="w-6 h-6 text-primary-foreground" />
            </div>
            <span className="text-2xl font-bold text-foreground">StateFlow</span>
          </Link>
          <h1 className="text-3xl font-bold text-foreground">Verify Email</h1>
          <p className="text-muted-foreground mt-2">
            {success ? 'Your email has been verified' : error ? 'Verification failed' : 'Confirm your email address'}
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-card border border-border rounded-xl p-6 shadow-sm">
          {error && (
            <div
              className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive flex items-center gap-2"
              role="alert"
            >
              <AlertCircleIcon className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {success && (
            <div
              className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-600 dark:text-green-400 flex items-center gap-2"
              role="status"
            >
              <CheckCircleIcon className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">{success}</span>
            </div>
          )}

          {!success && !error && !token && (
            <div className="space-y-4">
              <p className="text-center text-muted-foreground">
                No verification token provided. Please check your email for the verification link.
              </p>
              <form onSubmit={handleResend} className="space-y-4">
                <button
                  type="submit"
                  disabled={resending}
                  className="w-full py-2.5 px-4 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {resending ? 'Sending...' : 'Resend Verification Email'}
                </button>
              </form>
            </div>
          )}

          {success && (
            <div className="space-y-4">
              <div className="text-center">
                <div className="p-4 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                  <div className="flex items-center justify-center gap-3">
                    <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                      <CheckCircleIcon className="w-6 h-6 text-green-600 dark:text-green-400" />
                    </div>
                    <div className="text-left">
                      <h3 className="font-medium text-green-800 dark:text-green-200">
                        Email Verified!
                      </h3>
                      <p className="text-sm text-green-700 dark:text-green-300">
                        Your email address has been successfully verified. You can now access all features.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="text-center">
                <p className="text-sm text-muted-foreground">
                  <Link href="/login" className="text-primary hover:underline font-medium">
                    Sign In
                  </Link>
                </p>
              </div>
            </div>
          )}

          <div className="mt-6 text-center">
            <Link
              href="/login"
              className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
            >
              <ArrowLeftIcon className="w-4 h-4" />
              Back to Sign In
            </Link>
          </div>
        </div>

        {/* Note */}
        <div className="mt-6 p-4 rounded-lg bg-muted/50 border border-border">
          <h3 className="text-sm font-medium text-foreground mb-2">Didn't receive the email?</h3>
          <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
            <li>Check your spam or junk folder</li>
            <li>Make sure you entered the correct email address</li>
            <li>Try requesting a new verification email</li>
            <li>Contact support if you continue having issues</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center">Loading...</div>}>
      <VerifyEmailPageContent />
    </Suspense>
  );
}