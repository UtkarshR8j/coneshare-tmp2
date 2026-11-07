import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { authService } from '../services/authService'
import { APP_DISPLAY_VERSION } from '../lib/constants'
import { Button } from '../components/ui/Button'
import { useBranding } from '../contexts/BrandingProvider'
import { LanguagePicker } from '../components/common/LanguagePicker'
import { SplitBrandLayout } from '../components/auth/SplitBrandLayout'

function GoogleGlyph() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      className="h-5 w-5 shrink-0"
    >
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29C.47 8.24 0 10.06 0 12s.47 3.76 1.29 5.38l3.98-3.09z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75z"
      />
    </svg>
  )
}

function LoginPage() {
  const navigate = useNavigate()

  useEffect(() => {
    if (localStorage.getItem('access_token')) {
      navigate('/dashboard', { replace: true })
    }
  }, [navigate])
  const { t } = useTranslation()
  const { brandName, brandLogoUrl, brandWebsiteUrl, termsUrl, privacyPolicyUrl } = useBranding()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [showSignupLink, setShowSignupLink] = useState(false)

  useEffect(() => {
    let mounted = true

    const loadPublicSettings = async () => {
      try {
        const data = await authService.getPublicSettings()
        if (mounted) setShowSignupLink(Boolean(data?.enable_public_signup))
      } catch {
        if (mounted) setShowSignupLink(false)
      }
    }

    loadPublicSettings()
    return () => {
      mounted = false
    }
  }, [])

  useEffect(() => {
    document.title = `${t('auth.signIn')} - ${brandName}`;
  }, [brandName, t])

  const handleSubmit = async (event) => {
    event.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      await authService.login(email, password)
      // Redirect to homepage on successful login
      navigate('/dashboard')
    } catch {
      setError('auth.invalidCredentials')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <SplitBrandLayout brandName={brandName}>
      <div className="flex flex-col items-center">
        {brandLogoUrl ? (
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-card p-2 shadow-sm border border-border">
            <img
              src={brandLogoUrl}
              alt={`${brandName} logo`}
              className="h-12 w-12 object-contain"
            />
          </div>
        ) : null}
        <h2 className="text-center text-3xl font-extrabold text-gray-900 dark:text-white">
          {t('auth.signIn')}
        </h2>
        <p className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
          {t('auth.welcomeBack', { brandName })}
        </p>
      </div>

      <div>
        <a
          href="/api/v1/oidc/login/"
          className="flex w-full items-center justify-center gap-3 rounded-md bg-[#00677f] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#005a6e] active:scale-[0.98] active:bg-[#004e60] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          <GoogleGlyph />
          {t('auth.continueWithGoogle')}
        </a>

        <p className="my-5 text-center text-xs text-muted-foreground">
          {t('auth.orContinueWithEmail')}
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-4 rounded-md shadow-sm">
            <div>
              <label htmlFor="email" className="sr-only">
                {t('auth.email')}
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                className="relative block w-full appearance-none rounded-md border border-input bg-card px-3 py-2 text-foreground placeholder-muted-foreground focus:z-10 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary sm:text-sm"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="password" className="sr-only">
                {t('auth.password')}
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                className="relative block w-full appearance-none rounded-md border border-input bg-card px-3 py-2 text-foreground placeholder-muted-foreground focus:z-10 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary sm:text-sm"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <p className="text-sm text-destructive">{t(error)}</p>
          )}

          <div>
            <Button
              type="submit"
              size="lg"
              disabled={isLoading}
              className="w-full active:scale-[0.98] transition-transform"
            >
              {isLoading ? t('auth.signingIn') : t('auth.signIn')}
            </Button>
          </div>
        </form>

        <p className="mt-6 text-center text-[13px] leading-relaxed text-[#5f7076]">
          {t('auth.supportNote')}
        </p>

        {showSignupLink && (
          <p className="mt-4 text-center text-sm text-gray-600 dark:text-gray-400">
            {t('auth.newTo', { brandName })}{' '}
            <Link className="font-medium text-indigo-600 hover:text-indigo-500" to="/signup">
              {t('auth.signUp')}
            </Link>
          </p>
        )}
      </div>

      {/* Footer Links */}
      <div className="mt-auto pt-8 flex flex-col items-center justify-center gap-2 text-xs text-gray-400">
        <div className="flex items-center gap-3">
          <a
            href={brandWebsiteUrl || "https://www.coneshare.com/about"}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-600 transition-colors"
          >
            {t('auth.aboutBrand', { brandName: brandName || 'Coneshare' })}
          </a>
          <span className="text-gray-300">&bull;</span>
          <a
            href={termsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-600 transition-colors"
          >
            {t('auth.terms')}
          </a>
          <span className="text-gray-300">&bull;</span>
          <a
            href={privacyPolicyUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-600 transition-colors"
          >
            {t('auth.privacy')}
          </a>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-gray-400/80">
          {APP_DISPLAY_VERSION && (
            <>
              <span className="text-gray-300 select-none">&bull;</span>
              <span>{`ver-${APP_DISPLAY_VERSION}`}</span>
            </>
          )}
          <span className="text-gray-300 select-none">&bull;</span>
          <LanguagePicker />
        </div>
      </div>
    </SplitBrandLayout>
  )
}

export default LoginPage
