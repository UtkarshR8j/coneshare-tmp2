import { useCallback, useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { PasswordForm } from '../components/viewer/PasswordForm';
import { EmailForm } from '../components/viewer/EmailForm';
import { NDAForm } from '../components/viewer/NDAForm';
import { Skeleton } from '../components/ui/Skeleton';
import KilnDashboard from '../components/telemetry/KilnDashboard';
import { getShareLinkPublicMeta, getShareLinkTelemetry } from '../services/api';

/**
 * Public telemetry dashboard for a share link.
 *
 * The payload endpoint reuses the share link's own guards, so a 401
 * carrying a protectionType renders the same gate the viewer uses -
 * the telemetry page inherits the dataroom's password/email/NDA
 * protection rather than bypassing it.
 */
export function ShareLinkTelemetryPage() {
  const { t } = useTranslation();
  const { slug } = useParams();
  const [searchParams] = useSearchParams();

  const [payload, setPayload] = useState(null);
  const [publicMeta, setPublicMeta] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [protectionType, setProtectionType] = useState(null);
  const [refetchTrigger, setRefetchTrigger] = useState(0);

  useEffect(() => {
    let isCancelled = false;

    const fetchMeta = async () => {
      try {
        const res = await getShareLinkPublicMeta(slug);
        if (!isCancelled) setPublicMeta(res.data);
      } catch {
        // Meta is only used to pre-fill the gate; its failure is not
        // fatal because the telemetry call reports the real state.
      }
    };

    const fetchPayload = async () => {
      setIsLoading(true);
      setError(null);
      setProtectionType(null);
      try {
        const res = await getShareLinkTelemetry(slug);
        if (!isCancelled) setPayload(res.data);
      } catch (err) {
        if (isCancelled) return;
        const errData = err.response?.data || {
          message: 'Failed to load telemetry. The link may be invalid or expired.',
        };
        setError(errData);
        if (err.response?.status === 401 && errData?.protectionType) {
          setProtectionType(errData.protectionType);
        }
      } finally {
        if (!isCancelled) setIsLoading(false);
      }
    };

    fetchMeta();
    fetchPayload();

    return () => {
      isCancelled = true;
    };
  }, [slug, refetchTrigger, searchParams]);

  const handleGateSuccess = useCallback(() => {
    setRefetchTrigger((c) => c + 1);
  }, []);

  const backToViewer = useCallback(() => {
    window.location.assign(`/view/${slug}`);
  }, [slug]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#EAE6DF] p-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <Skeleton className="h-12 w-1/2" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (protectionType === 'password') {
    return (
      <PasswordForm slug={slug} onSuccess={handleGateSuccess} publicMeta={publicMeta} />
    );
  }

  if (protectionType === 'email') {
    return (
      <EmailForm
        slug={slug}
        onSuccess={handleGateSuccess}
        publicMeta={publicMeta}
        requiresConfirmation={error?.requiresConfirmation}
        emailToConfirm={error?.emailToConfirm}
        token={searchParams.get('accessToken')}
      />
    );
  }

  if (protectionType === 'nda') {
    return (
      <NDAForm
        slug={slug}
        onSuccess={handleGateSuccess}
        publicMeta={publicMeta}
      />
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#EAE6DF] p-6">
        <div className="max-w-md rounded-xl border border-black/10 bg-white/70 p-8 text-center backdrop-blur">
          <h1 className="mb-3 text-xl font-semibold text-[#1D1B19]">
            {t('telemetry.unavailableTitle', { defaultValue: 'Telemetry unavailable' })}
          </h1>
          <p className="text-sm text-black/70">{error.message}</p>
          <button
            type="button"
            onClick={backToViewer}
            className="mt-5 rounded-lg border border-black/15 bg-white/70 px-4 py-2 text-sm"
          >
            {t('common.back', { defaultValue: 'Back' })}
          </button>
        </div>
      </div>
    );
  }

  return (
    <KilnDashboard payload={payload} onBack={backToViewer} />
  );
}

export default ShareLinkTelemetryPage;
