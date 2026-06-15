import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50">
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-20">
        <div className="text-center">
          <h1 className="text-6xl font-bold text-gray-900 mb-6">
            🔨 Anvil
          </h1>
          <p className="text-2xl text-gray-600 mb-8">
            The Self-Verified Coding Agent
          </p>
          <p className="text-xl text-gray-500 max-w-3xl mx-auto mb-12">
            Anvil doesn't just generate code — it verifies it works. 
            Trained on 210K real agent traces that demonstrate the Plan → Execute → Verify → Recover pattern.
          </p>
          <div className="flex gap-4 justify-center">
            <Link 
              href="/getting-started"
              className="px-8 py-4 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 transition-colors"
            >
              Get Started
            </Link>
            <Link 
              href="/docs"
              className="px-8 py-4 bg-white text-purple-600 border-2 border-purple-600 rounded-lg font-semibold hover:bg-purple-50 transition-colors"
            >
              Documentation
            </Link>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="bg-white py-20">
        <div className="container mx-auto px-4">
          <h2 className="text-4xl font-bold text-center mb-12">Key Features</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="p-6 bg-purple-50 rounded-lg">
              <h3 className="text-2xl font-semibold mb-4">🔄 Verify Loop</h3>
              <p className="text-gray-600">
                Every change is verified with syntax checks, tests, and linting. 
                If verification fails, Anvil automatically diagnoses and recovers.
              </p>
            </div>
            <div className="p-6 bg-blue-50 rounded-lg">
              <h3 className="text-2xl font-semibold mb-4">🧠 Agent Memory</h3>
              <p className="text-gray-600">
                Persistent cross-session learning. Anvil remembers your preferences, 
                project context, and successful patterns.
              </p>
            </div>
            <div className="p-6 bg-green-50 rounded-lg">
              <h3 className="text-2xl font-semibold mb-4">🎯 Multi-Agent</h3>
              <p className="text-gray-600">
                Dispatch specialized subagents for complex tasks. 
                Build, plan, explore, and scout agents work together.
              </p>
            </div>
            <div className="p-6 bg-yellow-50 rounded-lg">
              <h3 className="text-2xl font-semibold mb-4">🛠️ Skill System</h3>
              <p className="text-gray-600">
                Install skills from GitHub or create your own. 
                Extend Anvil's capabilities with custom workflows.
              </p>
            </div>
            <div className="p-6 bg-red-50 rounded-lg">
              <h3 className="text-2xl font-semibold mb-4">🖥️ Desktop App</h3>
              <p className="text-gray-600">
                Native desktop experience with Tauri. 
                Beautiful UI for non-terminal users.
              </p>
            </div>
            <div className="p-6 bg-indigo-50 rounded-lg">
              <h3 className="text-2xl font-semibold mb-4">📡 TypeScript SDK</h3>
              <p className="text-gray-600">
                Full TypeScript SDK for integration. 
                Build custom tools and workflows in JavaScript/TypeScript.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Start Section */}
      <div className="bg-gray-900 text-white py-20">
        <div className="container mx-auto px-4">
          <h2 className="text-4xl font-bold text-center mb-12">Quick Start</h2>
          <div className="max-w-4xl mx-auto">
            <div className="bg-gray-800 rounded-lg p-6 mb-8">
              <h3 className="text-xl font-semibold mb-4">Install Anvil</h3>
              <pre className="bg-gray-900 p-4 rounded overflow-x-auto">
                <code className="text-green-400">
{`pip install fableforge-anvil-agent[all]`}
                </code>
              </pre>
            </div>
            <div className="bg-gray-800 rounded-lg p-6 mb-8">
              <h3 className="text-xl font-semibold mb-4">Run a Task</h3>
              <pre className="bg-gray-900 p-4 rounded overflow-x-auto">
                <code className="text-green-400">
{`anvil run "Fix the bug in main.py so tests pass"`}
                </code>
              </pre>
            </div>
            <div className="bg-gray-800 rounded-lg p-6">
              <h3 className="text-xl font-semibold mb-4">Start Web UI</h3>
              <pre className="bg-gray-900 p-4 rounded overflow-x-auto">
                <code className="text-green-400">
{`anvil serve
# Open http://localhost:8000`}
                </code>
              </pre>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-100 py-12">
        <div className="container mx-auto px-4 text-center">
          <p className="text-gray-600 mb-4">
            Built with ❤️ by the FableForge team
          </p>
          <div className="flex gap-6 justify-center">
            <a href="https://github.com/KingLabsA/anvil" className="text-purple-600 hover:text-purple-700">
              GitHub
            </a>
            <a href="/docs" className="text-purple-600 hover:text-purple-700">
              Documentation
            </a>
            <a href="https://pypi.org/project/fableforge-anvil-agent/" className="text-purple-600 hover:text-purple-700">
              PyPI
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
