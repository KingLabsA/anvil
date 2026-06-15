export default function CoreConcepts() {
  return (
    <div className="min-h-screen bg-white">
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <h1 className="text-5xl font-bold mb-8">Core Concepts</h1>
        
        <div className="prose prose-lg max-w-none">
          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">The Verify Loop</h2>
            <p className="text-gray-600 mb-4">
              Anvil's core innovation is the <strong>Plan → Execute → Verify → Recover</strong> loop. 
              Unlike other coding agents that generate code and hope it works, Anvil verifies every change.
            </p>
            <div className="bg-purple-50 p-6 rounded-lg my-6">
              <h3 className="text-xl font-semibold mb-3">The Loop</h3>
              <ol className="list-decimal list-inside space-y-2 text-gray-700">
                <li><strong>Plan:</strong> Break the task into small, verifiable steps</li>
                <li><strong>Execute:</strong> Implement each step using tools</li>
                <li><strong>Verify:</strong> Check syntax, run tests, lint code</li>
                <li><strong>Recover:</strong> If verification fails, diagnose and fix</li>
              </ol>
            </div>
            <p className="text-gray-600">
              This loop continues until all steps pass verification or max retries are reached.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Agents</h2>
            <p className="text-gray-600 mb-4">
              Anvil uses a multi-agent architecture with specialized roles:
            </p>
            <div className="grid md:grid-cols-2 gap-4 my-6">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Build Agent</h3>
                <p className="text-sm text-gray-600">
                  Primary coding agent with full tool access. Handles most tasks.
                </p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Plan Agent</h3>
                <p className="text-sm text-gray-600">
                  Read-only planning agent. Analyzes and suggests without modifying.
                </p>
              </div>
              <div className="bg-yellow-50 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Explore Agent</h3>
                <p className="text-sm text-gray-600">
                  Read-only exploration subagent. Investigates code structure.
                </p>
              </div>
              <div className="bg-red-50 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Scout Agent</h3>
                <p className="text-sm text-gray-600">
                  Specialized subagent for specific reconnaissance tasks.
                </p>
              </div>
            </div>
            <p className="text-gray-600">
              You can dispatch subagents using the <code className="bg-gray-200 px-2 py-1 rounded">@agent</code> syntax 
              or the <code className="bg-gray-200 px-2 py-1 rounded">task</code> tool.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Tools</h2>
            <p className="text-gray-600 mb-4">
              Anvil has access to a set of tools for interacting with the codebase:
            </p>
            <div className="bg-gray-50 p-6 rounded-lg my-6">
              <ul className="space-y-2 text-gray-700">
                <li><code className="bg-gray-200 px-2 py-1 rounded">bash</code> - Run shell commands</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">read</code> - Read file contents</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">write</code> - Write new files</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">edit</code> - Edit existing files</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">grep</code> - Search file contents</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">glob</code> - Find files by pattern</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">ls</code> - List directory contents</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">task</code> - Dispatch subagents</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">skill</code> - Load specialized skills</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">press</code> - Generate API wrappers</li>
              </ul>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Verification</h2>
            <p className="text-gray-600 mb-4">
              Anvil's verification pipeline checks:
            </p>
            <ul className="list-disc list-inside text-gray-600 space-y-2 mb-4">
              <li><strong>Syntax:</strong> Code parses correctly</li>
              <li><strong>Tests:</strong> Test suite passes</li>
              <li><strong>Lint:</strong> Code style is consistent</li>
              <li><strong>Types:</strong> Type checking passes (optional)</li>
            </ul>
            <p className="text-gray-600">
              If verification fails, Anvil enters recovery mode and attempts to fix the issues automatically.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Skills</h2>
            <p className="text-gray-600 mb-4">
              Skills are reusable instruction sets that extend Anvil's capabilities. 
              They're defined in <code className="bg-gray-200 px-2 py-1 rounded">SKILL.md</code> files and can be:
            </p>
            <ul className="list-disc list-inside text-gray-600 space-y-2 mb-4">
              <li>Installed from GitHub repositories</li>
              <li>Created locally in your project</li>
              <li>Shared with the community</li>
            </ul>
            <p className="text-gray-600">
              Skills are loaded on-demand using the <code className="bg-gray-200 px-2 py-1 rounded">skill</code> tool.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Memory</h2>
            <p className="text-gray-600 mb-4">
              Anvil has persistent memory across sessions. It remembers:
            </p>
            <ul className="list-disc list-inside text-gray-600 space-y-2 mb-4">
              <li><strong>Preferences:</strong> Your coding style and preferences</li>
              <li><strong>Projects:</strong> Project-specific context</li>
              <li><strong>Patterns:</strong> Successful approaches</li>
              <li><strong>Mistakes:</strong> Things to avoid</li>
              <li><strong>Facts:</strong> General knowledge</li>
            </ul>
            <p className="text-gray-600">
              Memory is automatically extracted from task completions and injected into future tasks.
            </p>
          </section>

          <section>
            <h2 className="text-3xl font-semibold mb-4">Next Steps</h2>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>
                <a href="/docs/cli" className="text-purple-600 hover:text-purple-700">
                  CLI Reference →
                </a>
              </li>
              <li>
                <a href="/docs/memory" className="text-purple-600 hover:text-purple-700">
                  Agent Memory Guide →
                </a>
              </li>
              <li>
                <a href="/docs/skills" className="text-purple-600 hover:text-purple-700">
                  Skills Documentation →
                </a>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
