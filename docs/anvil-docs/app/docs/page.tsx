import Link from 'next/link';

export default function Docs() {
  const sections = [
    {
      title: "Core Concepts",
      description: "Understand Anvil's architecture and verify loop",
      link: "/docs/core-concepts"
    },
    {
      title: "CLI Reference",
      description: "Complete CLI command reference",
      link: "/docs/cli"
    },
    {
      title: "Web UI",
      description: "Using the web interface",
      link: "/docs/web-ui"
    },
    {
      title: "Agent Memory",
      description: "Persistent cross-session learning",
      link: "/docs/memory"
    },
    {
      title: "Skills",
      description: "Installing and creating skills",
      link: "/docs/skills"
    },
    {
      title: "TypeScript SDK",
      description: "Integration with JavaScript/TypeScript",
      link: "/docs/typescript-sdk"
    },
    {
      title: "Desktop App",
      description: "Native desktop application",
      link: "/docs/desktop"
    },
    {
      title: "Configuration",
      description: "Customizing Anvil's behavior",
      link: "/docs/configuration"
    }
  ];

  return (
    <div className="min-h-screen bg-white">
      <div className="container mx-auto px-4 py-12 max-w-6xl">
        <h1 className="text-5xl font-bold mb-8">Documentation</h1>
        <p className="text-xl text-gray-600 mb-12">
          Everything you need to know about Anvil
        </p>

        <div className="grid md:grid-cols-2 gap-6">
          {sections.map((section, index) => (
            <Link 
              key={index}
              href={section.link}
              className="block p-6 border-2 border-gray-200 rounded-lg hover:border-purple-600 hover:shadow-lg transition-all"
            >
              <h2 className="text-2xl font-semibold mb-2">{section.title}</h2>
              <p className="text-gray-600">{section.description}</p>
            </Link>
          ))}
        </div>

        <div className="mt-16 p-8 bg-purple-50 rounded-lg">
          <h2 className="text-3xl font-semibold mb-4">Quick Links</h2>
          <div className="grid md:grid-cols-3 gap-4">
            <a 
              href="https://github.com/KingLabsA/anvil" 
              className="text-purple-600 hover:text-purple-700"
            >
              GitHub Repository →
            </a>
            <a 
              href="https://pypi.org/project/fableforge-anvil-agent/" 
              className="text-purple-600 hover:text-purple-700"
            >
              PyPI Package →
            </a>
            <a 
              href="/getting-started" 
              className="text-purple-600 hover:text-purple-700"
            >
              Getting Started →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
