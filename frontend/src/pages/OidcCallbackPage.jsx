import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { authService } from '../services/authService'

/**
 * Landing pad for the OIDC flow: the backend redirects here with the JWTs in
 * the URL fragment (`#access=...&refresh=...`) or an `error=...` when
 * something went wrong upstream.
 */
function OidcCallbackPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [error, setError] = useState(null)

  useEffect(() => {
    const result = authService.storeTokenFragment(window.location.hash)

    if (result.error) {
      setError(result.error)
      window.history.replaceState(null, '', window.location.pathname)
      return
    }

    window.history.replaceState(null, '', window.location.pathname)
    navigate('/dashboard', { replace: true })
  }, [navigate])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-foreground">
      {error ? (
        <>
          <p className="text-sm font-medium text-destructive">{t('auth.ssoFailed')}</p>
          <a
            href="/login"
            className="text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            {t('auth.signIn')}
          </a>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">{t('auth.signingIn')}</p>
      )}
    </div>
  )
}

export default OidcCallbackPage
