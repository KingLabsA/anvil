export default function GettingStarted() {
  return (
    <div className="min-h-screen bg-white">
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <h1 className="text-5xl font-bold mb-8">Getting Started</h1>
        
        <div className="prose prose-lg max-w-none">
          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Installation</h2>
            <p className="text-gray-600 mb-4">
              Install Anvil with all optional dependencies:
            </p>
            <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto">
              <code className="text-gray-800">
{`pip install fableforge-anvil-agent[all]`}
              </code>
            </pre>
            <p className="text-gray-600 mt-4">
              Or install specific extras:
            </p>
            <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto">
              <code className="text-gray-800">
{`# Web UI
pip install fableforge-anvil-agent[web]

# Local models
pip install fableforge-anvil-agent[local]

# API models (OpenAI, Anthropic)
pip install fableforge-anvil-agent[api]`}
              </code>
            </pre>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">First Task</h2>
            <p className="text-gray-600 mb-4">
              Run your first task with Anvil:
            </p>
            <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto">
              <code className="text-gray-800">
{`anvil run "Create a Python function that calculates fibonacci numbers"`}
              </code>
            </pre>
            <p className="text-gray-600 mt-4">
              Anvil will:
            </p>
            <ol className="list-decimal list-inside text-gray-600 space-y-2">
              <li>Plan the implementation</li>
              <li>Execute the plan step by step</li>
              <li>Verify each change with tests and linting</li>
              <li>Recover automatically if verification fails</li>
            </ol>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Web UI</h2>
            <p className="text-gray-600 mb-4">
              Start the web interface:
            </p>
            <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto">
              <code className="text-gray-800">
{`anvil serve
# Open http://localhost:8000`}
              </code>
            </pre>
            <p className="text-gray-600 mt-4">
              The web UI provides:
            </p>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>Interactive chat interface</li>
              <li>Real-time task progress</li>
              <li>Session history</li>
              <li>WebSocket streaming</li>
            </ul>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Desktop App</h2>
            <p className="text-gray-600 mb-4">
              For a native desktop experience, build the Tauri app:
            </p>
            <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto">
              <code className="text-gray-800">
{`cd desktop/anvil-desktop
npm install
npm run tauri build`}
              </code>
            </pre>
            <p className="text-gray-600 mt-4">
              The built app will be in <code className="bg-gray-200 px-2 py-1 rounded">src-tauri/target/release/bundle/</code>
            </p>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Configuration</h2>
            <p className="text-gray-600 mb-4">
              Create <code className="bg-gray-200 px-2 py-1 rounded">.anvil.json</code> in your project root:
            </p>
            <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto">
              <code className="text-gray-800">
{`{
  "model": {
    "model": "local",
    "max_tokens": 4096
  },
  "verify": {
    "enabled": true,
    "auto_recover": true,
    "max_retries": 3
  },
  "tools": {
    "allow_shell": true,
    "sandbox": false
  }
}`}
              </code>
            </pre>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Next Steps</h2>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>
                <a href="/docs" className="text-purple-600 hover:text-purple-700">
                  Read the full documentation
                </a>
              </li>
              <li>
                <a href="/guides" className="text-purple-600 hover:text-purple-700">
                  Check out the guides
                </a>
              </li>
              <li>
                <a href="/api" className="text-purple-600 hover:text-purple-700">
                  Explore the API reference
                </a>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
