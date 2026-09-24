import Link from "next/link";

export default function Home() {
  const links = [
    {
      href: "/assistant",
      title: "Memory Assistant",
      description: "Talk to your full archive",
    },
    {
      href: "/clone",
      title: "Clone",
      description: "Chat with your first-person persona",
    },
    {
      href: "/entries",
      title: "Entries",
      description: "Write or record today's memory",
    },
    {
      href: "/memories",
      title: "Memories",
      description: "View and manage your memories",
    },
    {
      href: "/digest",
      title: "Release Digest",
      description: "Review memories pending release",
    },
    {
      href: "/seed",
      title: "Seed Interview",
      description: "Answer questions about yourself",
    },
    {
      href: "/traits",
      title: "Traits",
      description: "Review your inferred traits",
    },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white dark:from-slate-900 dark:to-slate-800">
      <div className="max-w-2xl mx-auto px-4 py-16">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-slate-900 dark:text-white mb-4">
            Keepsake
          </h1>
          <p className="text-xl text-slate-600 dark:text-slate-300 mb-2">
            A personal memory archive
          </p>
          <p className="text-slate-500 dark:text-slate-400">
            Preserve your story, share your wisdom
          </p>
        </div>

        <div className="grid gap-4">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="block p-6 rounded-lg border border-slate-200 dark:border-slate-700 hover:border-slate-400 dark:hover:border-slate-500 hover:shadow-lg transition-all bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700"
            >
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                {link.title}
              </h2>
              <p className="text-slate-600 dark:text-slate-400">
                {link.description}
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
