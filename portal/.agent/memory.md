### 2026-07-13 Session Entry
- **Category:** Gotcha
- **Context/Implication:** The portal uses Next.js static exports (`output: 'export'`), which compiles to plain static HTML files. Using dynamic server-side redirection methods (like calling `redirect()` from `next/navigation`) crashes during the static build generation process.
- **Resolution/Action:** Implement SEO-friendly redirects on static export pages by defining static page metadata in a Server Component containing alternates and refresh metadata tags:
  ```javascript
  export const metadata = {
    alternates: { canonical: '/new-target' },
    other: { 'refresh': '0; url=/new-target' }
  };
  ```

### 2026-07-13 Session Entry
- **Category:** Architecture Choice / SEO
- **Context/Implication:** To improve search engine visibility and support rich expandable snippet accordions on SERP pages, landing pages with static FAQs should include structured FAQ data.
- **Resolution/Action:** Add structured `FAQPage` JSON-LD schemas inside Next.js App Router Server Components by rendering a script tag:
  ```javascript
  const faqJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faqs.map((faq) => ({
      '@type': 'Question',
      name: faq.q,
      acceptedAnswer: { '@type': 'Answer', text: faq.a }
    }))
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />
      {/* Content */}
    </>
  );
  ```

### 2026-09-29 Session Entry
- **Category:** Tooling Update
- **Context/Implication:** Vitest with jsdom environment and React Testing Library is configured for the Next.js portal package to verify component rendering, navigation, and localization without manual browser/curl inspections.
- **Resolution/Action:** Run unit tests for portal via `make test.portal` from root, or `cd portal && npm run test:run`. Tests are placed in `portal/src/tests/**/*.test.jsx`.

### 2026-09-29 Session Entry
- **Category:** Gotcha
- **Context/Implication:** In Next.js App Router, subroute layouts (`portal/app/zh/layout.js`) nest inside the root layout (`portal/app/layout.js`). Rendering `<Header />` and `<Footer />` in both causes duplicate UI headers/footers to appear on subroute pages.
- **Resolution/Action:** Mount global layout elements (`<Header />`, `<Footer />`) solely in root `layout.js`, and let components dynamically adapt their localized text and links via `usePathname().startsWith('/zh')`.

