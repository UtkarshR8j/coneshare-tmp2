import { useTranslation } from 'react-i18next'

/**
 * Full-screen split-brand shell used by the login surfaces: a photo panel with
 * the white wordmark and tagline on the left, the interactive column on the
 * right. Collapses to a photo band above the form below `md`.
 */
export function SplitBrandLayout({ brandName, children }) {
  const { t } = useTranslation()

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground md:flex-row">
      <aside
        className="relative flex min-h-[220px] w-full flex-col overflow-hidden px-7 py-8 text-white md:min-h-screen md:w-[44%] md:px-14 md:py-[52px]"
        style={{
          backgroundImage:
            'linear-gradient(180deg, rgba(20,40,50,.75) 0%, rgba(16,33,41,.87) 100%), url(/brand/left-panel.jpg?v=2)',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        <img
          src="/brand/longstraw-carbon-logo-white.png"
          alt={`${brandName} logo`}
          className="h-[72px] w-auto self-start object-contain"
        />
        <p className="mt-auto max-w-[16ch] pt-10 text-[23px] font-semibold leading-snug tracking-tight md:text-[33px]">
          {t('auth.tagline')}
        </p>
      </aside>

      <main className="flex flex-1 flex-col items-center justify-center px-4 py-12">
        <div className="w-full max-w-md space-y-8">{children}</div>
      </main>
    </div>
  )
}

export default SplitBrandLayout
