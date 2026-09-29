import Link from 'next/link';

export const metadata = {
  title: '关于 Coneshare | 为什么我们打造私有化文档分享平台',
  description:
    '深入了解我们创立 Coneshare 的初衷，以及它如何在您现有存储之上提供虚拟资料室与深度阅读追踪。',
  alternates: {
    canonical: '/zh/about',
  },
};

const principles = [
  {
    title: '坚持保留存储归属权',
    body:
      '企业早已拥有值得信赖的存储工具。Coneshare 直接在其上叠加权限管控与追踪能力，无需强制数据迁移。',
  },
  {
    title: '拥抱开源透明',
    body:
      'Coneshare 完全开源。您可以自由审查代码逻辑，验证敏感数据在底层的流转机制，并放心地部署在企业内部服务器上。',
  },
  {
    title: '全面的开放 API 生态',
    body:
      '每一项分享配置、审计日志与自动化触发器均可通过 API 编程调用，能够轻松与内部运维脚本、自动化管道及 AI 智能体无缝对接。',
  },
];

const signupUrl = 'https://app.coneshare.com/signup';

export default function ZhAboutPage() {
  return (
    <div className="bg-white py-20 sm:py-28">
      <div className="mx-auto max-w-5xl px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">关于 Coneshare</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
            掌控文档安全，无需牺牲基础设施自主权
          </h1>
        </div>

        <section className="mx-auto mt-16 max-w-4xl sm:mt-20">
          <div className="prose prose-lg max-w-none text-gray-700">
            <h2 className="text-gray-900">我们解决的核心痛点</h2>
            <p>
              商业融资、投融资尽调、法务合规交涉与大客户商务谈判，都离不开机密文件的对外传输。然而一旦文件离开企业内部，您必须清楚知道谁在什么时候打开了文件、在核心条款页上停留了多长时间，以及是否被下载复制。
            </p>
            <p>
              传统企业网盘非常擅长内部员工协作，但一旦向外部发送链接，就几乎失去了所有掌控力。Coneshare 填补了这一鸿沟：它在您现有存储上原生叠加密码保护、保密协议门禁、动态身份水印、逐页访客分析以及 Webhook 自动化能力。
            </p>
          </div>
        </section>

        <section className="mx-auto mt-16 max-w-4xl border-t border-gray-200 pt-12">
          <div className="grid gap-8 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">技术理念</p>
              <h2 className="mt-3 text-2xl font-bold tracking-tight text-gray-900">我们的产品原则</h2>
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
              <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">面向未来</p>
              <h2 className="mt-3 text-2xl font-bold tracking-tight text-gray-900">AI 时代的研发与产品理念</h2>
            </div>
            <div className="space-y-6 lg:col-span-8">
              <div className="rounded-xl border border-gray-200 bg-gray-50/50 p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-900 text-white text-sm font-bold">1</span>
                  <h3 className="text-base font-semibold text-gray-900">借助 AI 提升研发效率，把节省的成本返还给用户</h3>
                </div>
                <p className="mt-3 text-sm leading-6 text-gray-600">
                  我们在日常研发与测试中深度使用 AI 编程工具，让小团队也能以更低的人力负担、远快于传统团队的节奏交付稳定可靠的功能。大幅降低的开发与维护成本，直接反映在我们的定价策略上：开源核心版永久免费，企业级私有部署的费用也仅为传统商业 SaaS 的几分之一。
                </p>
              </div>

              <div className="rounded-xl border border-gray-200 bg-gray-50/50 p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-900 text-white text-sm font-bold">2</span>
                  <h3 className="text-base font-semibold text-gray-900">将 AI Agent 融入产品，打造更实用的智能文档空间</h3>
                </div>
                <p className="mt-3 text-sm leading-6 text-gray-600">
                  虚拟资料室不应该只是静态存放和查看文件的地方。Coneshare 正通过标准 MCP（Model Context Protocol）协议对接外部 AI Agent 生态，并在产品内逐步内置文档智能问答、尽调查验助手、内容自动摘要与敏感信息审查，让资料室真正具备主动分析与协同能力。
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto mt-16 max-w-4xl border-t border-gray-200 pt-12">
          <div className="grid gap-8 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <p className="text-sm font-semibold uppercase tracking-wide text-gray-600">适用场景</p>
              <h2 className="mt-3 text-2xl font-bold tracking-tight text-gray-900">何时选择 Coneshare</h2>
            </div>
            <div className="space-y-8 lg:col-span-8">
              <div>
                <h3 className="text-base font-semibold text-gray-900">特别契合的场景</h3>
                <ul className="mt-4 space-y-3 text-sm leading-6 text-gray-600">
                  <li>使用 Nextcloud、Google Drive 或 Dropbox，希望获得更强大的对外分享管控能力。</li>
                  <li>需要专业虚拟资料室，但拒绝将海量业务资料迁移至第三方商业 SaaS 服务商。</li>
                  <li>商业融资、并购尽调、法务合规及大客户招投标中，需要高度依赖访客阅读行为数据。</li>
                  <li>对数据主权和隐私合规有严苛要求的团队，偏好在自有服务器上私有化运行。</li>
                </ul>
              </div>
              <div>
                <h3 className="text-base font-semibold text-gray-900">不适用的场景</h3>
                <ul className="mt-4 space-y-3 text-sm leading-6 text-gray-600">
                  <li>普通文件日常传输，标准网盘生成的公共共享链接已完全能满足要求。</li>
                  <li>寻求全面替换底层企业网络挂载盘或对象存储的底层存储系统。</li>
                  <li>仅关注内部多人在线协同编辑，而不需要对外访问门禁与追踪。</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section className="mx-auto mt-14 max-w-4xl rounded-lg bg-gray-900 px-6 py-8 text-white sm:px-8">
          <div className="grid gap-6 lg:grid-cols-12 lg:items-center">
            <div className="lg:col-span-8">
              <h2 className="text-2xl font-bold tracking-tight">体验在线演示环境</h2>
              <p className="mt-3 text-sm leading-6 text-gray-300">
                在将 Coneshare 部署到企业专属服务器之前，您可以在我们的公共演示环境中完整测试文档阅读器、权限管控及分析看板。
              </p>
            </div>
            <div className="flex flex-wrap gap-3 lg:col-span-4 lg:justify-end">
              <Link href="/demo" className="rounded-md bg-white px-4 py-2.5 text-sm font-semibold text-gray-900 hover:bg-gray-100">
                在线演示
              </Link>
              <Link href={signupUrl} target="_blank" rel="noopener noreferrer" className="rounded-md bg-white px-4 py-2.5 text-sm font-semibold text-gray-900 hover:bg-gray-100">
                立即开始
              </Link>
              <Link href="https://github.com/coneshare/coneshare" target="_blank" rel="noopener noreferrer" className="rounded-md border border-white/30 px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/10">
                GitHub 源码
              </Link>
            </div>
          </div>
        </section>

        <section className="mx-auto mt-12 max-w-4xl text-sm leading-6 text-gray-600">
          <p>
            商务采购咨询或安全合规评估，欢迎联系{' '}
            <a href="mailto:sales@coneshare.com" className="font-semibold text-gray-900 hover:text-gray-700">
              sales@coneshare.com
            </a>
            。技术支持或漏洞提报，请发送至{' '}
            <a href="mailto:dev@coneshare.com" className="font-semibold text-gray-900 hover:text-gray-700">
              dev@coneshare.com
            </a>
            。
          </p>
        </section>
      </div>
    </div>
  );
}
