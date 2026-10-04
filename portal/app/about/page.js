import Link from 'next/link';

export const metadata = {
  title: 'About Kalinga | Why We Built Self-Hosted Document Sharing',
  description:
    'Why we built Kalinga and how it brings virtual data rooms and tracking to your existing storage.',
  alternates: {
    canonical: '/about',
  },
};

const principles = [
  {
    title: 'Keep storage ownership clear',
    body:
      'Teams already have storage tools they trust. Kalinga adds sharing controls and tracking on top without forcing a storage migration.',
  },
  {
    title: 'Build in the open',
    body:
      'Kalinga is open source. You can inspect the code, verify how data is handled, and deploy on your own servers.',
  },
  {
    title: 'Work through open APIs',
    body:
      'Every sharing feature, analytics log, and automation rule is available via API, making it easy to connect with internal scripts and AI agents.',
  },
];

const signupUrl = 'https://app.coneshare.com/signup';

export default function AboutPage() {
  return (
    <div className="bg-white py-20 sm:py-28">
      <div className="mx-auto max-w-5xl px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">About Kalinga</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
            Document control without giving up infrastructure ownership
          </h1>
        </div>

        <section className="mx-auto mt-16 max-w-4xl sm:mt-20">
          <div className="prose prose-lg max-w-none text-gray-700">
            <h2 className="text-gray-900">The problem we solve</h2>
            <p>
              Fundraising, due diligence, legal exchanges, and sales deals all require secure file sharing. Once a document leaves your company, you need to know who opened it, how much time they spent on each page, and whether it was downloaded.
            </p>
            <p>
              Cloud storage is great for internal collaboration, but it offers little control once files are shared externally. Kalinga fills that gap by adding password gates, NDA agreements, dynamic watermarking, viewer analytics, and webhook automation to your storage.
            </p>
          </div>
        </section>

        <section className="mx-auto mt-16 max-w-4xl border-t border-gray-200 pt-12">
          <div className="grid gap-8 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">Principles</p>
              <h2 className="mt-3 text-2xl font-bold tracking-tight text-gray-900">How we build</h2>
            </div>
            <div className="space-y-8 lg:col-span-8">
              {principles.map((principle, index) => (
                <div key={principle.title} className="grid gap-4 sm:grid-cols-12">
                  <p className="text-sm font-semibold text-gray-400 sm:col-span-2">
                    {String(index + 1).padStart(2, '0')}
                  </p>
                  <div className="sm:col-span-10">
                    <h3 className="text-base font-semibold text-gray-900">{principle.title}</h3>
                    <p className="mt-2 text-sm leading-6 text-gray-600">{principle.body}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto mt-16 max-w-4xl border-t border-gray-200 pt-12">
          <div className="grid gap-8 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">Looking Ahead</p>
              <h2 className="mt-3 text-2xl font-bold tracking-tight text-gray-900">Engineering & Product Philosophy in the AI Era</h2>
            </div>
            <div className="space-y-6 lg:col-span-8">
              <div className="rounded-xl border border-gray-200 bg-gray-50/50 p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-900 text-white text-sm font-bold">1</span>
                  <h3 className="text-base font-semibold text-gray-900">Building faster with AI, passing the savings to users</h3>
                </div>
                <p className="mt-3 text-sm leading-6 text-gray-600">
                  We use modern AI coding tools and automated testing throughout our development process. This lets our small team ship reliable features much faster than a traditional team, with far lower overhead. Those cost savings go straight into our pricing: our core platform is open source and free forever, while teams get self-hosted enterprise control at a fraction of standard SaaS rates.
                </p>
              </div>

              <div className="rounded-xl border border-gray-200 bg-gray-50/50 p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-900 text-white text-sm font-bold">2</span>
                  <h3 className="text-base font-semibold text-gray-900">Integrating AI agents into the workspace</h3>
                </div>
                <p className="mt-3 text-sm leading-6 text-gray-600">
                  A secure data room should do more than just store and display static files. We connect Kalinga to external AI agents through open standards like Model Context Protocol (MCP). We are also building native AI tools directly into the workspace, including document Q&A, diligence review assistants, automatic summaries, and sensitive data inspection.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto mt-16 max-w-4xl border-t border-gray-200 pt-12">
          <div className="grid gap-8 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">Fit</p>
              <h2 className="mt-3 text-2xl font-bold tracking-tight text-gray-900">When to use Kalinga</h2>
            </div>
            <div className="space-y-8 lg:col-span-8">
              <div>
                <h3 className="text-base font-semibold text-gray-900">A good fit for</h3>
                <ul className="mt-4 space-y-3 text-sm leading-6 text-gray-600">
                  <li>Teams using Nextcloud, Google Drive, or Dropbox who want better sharing controls.</li>
                  <li>Organizations that need virtual data rooms without migrating files to another vendor.</li>
                  <li>Fundraising, diligence, legal, and sales workflows where viewer analytics matter.</li>
                  <li>Security-conscious teams that require self-hosted software for data sovereignty.</li>
                </ul>
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900">Not a good fit for</h3>
                <ul className="mt-4 space-y-3 text-sm leading-6 text-gray-600">
                  <li>Simple file transfers where a standard cloud share link is enough.</li>
                  <li>Teams looking to replace their primary storage system.</li>
                  <li>Internal team collaboration that does not require access gates or tracking.</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto mt-14 max-w-4xl rounded-lg bg-gray-900 px-6 py-8 text-white sm:px-8">
          <div className="grid gap-6 lg:grid-cols-12 lg:items-center">
            <div className="lg:col-span-8">
              <h2 className="text-2xl font-bold tracking-tight">Try the demo</h2>
              <p className="mt-3 text-sm leading-6 text-gray-300">
                Test the viewer, access controls, and analytics in our public demo environment before installing Kalinga on your own servers.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 lg:col-span-4 lg:justify-end">
              <Link href="/demo" className="rounded-md bg-white px-4 py-2.5 text-sm font-semibold text-gray-900 hover:bg-gray-100">
                Live Demo
              </Link>
              <Link href={signupUrl} target="_blank" rel="noopener noreferrer" className="rounded-md bg-white px-4 py-2.5 text-sm font-semibold text-gray-900 hover:bg-gray-100">
                Get Started
              </Link>
              <Link href="https://github.com/coneshare/coneshare" target="_blank" rel="noopener noreferrer" className="rounded-md border border-white/30 px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/10">
                GitHub
              </Link>
            </div>
          </div>
        </section>

        <section className="mx-auto mt-12 max-w-4xl text-sm leading-6 text-gray-600">
          <p>
            For sales, procurement, or security questions, contact{' '}
            <a href="mailto:sales@coneshare.com" className="font-semibold text-gray-900 hover:text-gray-700">
              sales@coneshare.com
            </a>
            . For technical support and security disclosures, contact{' '}
            <a href="mailto:dev@coneshare.com" className="font-semibold text-gray-900 hover:text-gray-700">
              dev@coneshare.com
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
