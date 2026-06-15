export default function CLIReference() {
  return (
    <div className="min-h-screen bg-white">
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <h1 className="text-5xl font-bold mb-8">CLI Reference</h1>
        
        <div className="prose prose-lg max-w-none">
          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Main Commands</h2>
            
            <div className="space-y-6">
              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil run</code>
                </h3>
                <p className="text-gray-600 mb-3">Execute a task with self-verification</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil run "Fix the bug in main.py"
anvil run --model gpt-4o "Refactor auth module"
anvil run --flow plan "Design new feature"`}
                </pre>
                <p className="text-sm text-gray-500 mt-2">
                  Options: <code>--model</code>, <code>--flow</code>, <code>--max-iterations</code>, <code>--no-verify</code>
                </p>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil chat</code>
                </h3>
                <p className="text-gray-600 mb-3">Interactive chat mode</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil chat
anvil chat --agent plan`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil serve</code>
                </h3>
                <p className="text-gray-600 mb-3">Start web UI server</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil serve --port 8000
# Open http://localhost:8000`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil verify</code>
                </h3>
                <p className="text-gray-600 mb-3">Verify code without making changes</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil verify src/
anvil verify --checks syntax,lint src/main.py`}
                </pre>
              </div>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Session Management</h2>
            
            <div className="space-y-6">
              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil sessions</code>
                </h3>
                <p className="text-gray-600 mb-3">List past sessions</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil sessions`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil share</code>
                </h3>
                <p className="text-gray-600 mb-3">Share a session</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil share abc123
anvil share abc123 --link
anvil share abc123 --output session.json`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil import-session</code>
                </h3>
                <p className="text-gray-600 mb-3">Import a session</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil import-session session.json
anvil import-session anvil://...`}
                </pre>
              </div>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Skills</h2>
            
            <div className="space-y-6">
              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil skills search</code>
                </h3>
                <p className="text-gray-600 mb-3">Search for skills</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil skills search react
anvil skills search --limit 10 typescript`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil skills install</code>
                </h3>
                <p className="text-gray-600 mb-3">Install a skill</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil skills install https://github.com/user/skill
anvil skills install ./local-skill --name my-skill`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil skills list</code>
                </h3>
                <p className="text-gray-600 mb-3">List installed skills</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil skills list`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil skills remove</code>
                </h3>
                <p className="text-gray-600 mb-3">Remove a skill</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil skills remove skill-name`}
                </pre>
              </div>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Memory</h2>
            
            <div className="space-y-6">
              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil memory list</code>
                </h3>
                <p className="text-gray-600 mb-3">List stored memories</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil memory list
anvil memory list --category preference
anvil memory list --limit 20`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil memory add</code>
                </h3>
                <p className="text-gray-600 mb-3">Add a memory</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil memory add --category preference \\
  --content "User prefers TypeScript" \\
  --importance 0.8`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil memory recall</code>
                </h3>
                <p className="text-gray-600 mb-3">Recall relevant memories</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil memory recall "React TypeScript"`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil memory clear</code>
                </h3>
                <p className="text-gray-600 mb-3">Clear memories</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil memory clear
anvil memory clear --category mistake`}
                </pre>
              </div>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Agents</h2>
            
            <div className="space-y-6">
              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil agents list</code>
                </h3>
                <p className="text-gray-600 mb-3">List available agents</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil agents list`}
                </pre>
              </div>

              <div className="bg-gray-50 p-6 rounded-lg">
                <h3 className="text-xl font-semibold mb-2">
                  <code className="text-purple-600">anvil agents create</code>
                </h3>
                <p className="text-gray-600 mb-3">Create a custom agent</p>
                <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`anvil agents create my-agent`}
                </pre>
              </div>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Global Options</h2>
            <div className="bg-gray-50 p-6 rounded-lg">
              <ul className="space-y-2 text-gray-700">
                <li><code className="bg-gray-200 px-2 py-1 rounded">--model, -m</code> - Model to use (shellwhisperer, local, gpt-4o, etc.)</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">--agent, -a</code> - Agent to use (build, plan, explore, scout)</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">--config, -c</code> - Config file path</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">--verbose, -v</code> - Verbose output</li>
                <li><code className="bg-gray-200 px-2 py-1 rounded">--quiet, -q</code> - Minimal output</li>
              </ul>
            </div>
          </section>

          <section>
            <h2 className="text-3xl font-semibold mb-4">Examples</h2>
            <div className="space-y-4">
              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="text-sm text-gray-600 mb-2">Run a task with GPT-4o:</p>
                <pre className="bg-gray-900 text-green-400 p-3 rounded overflow-x-auto text-sm">
{`anvil run --model gpt-4o "Add error handling to API endpoints"`}
                </pre>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="text-sm text-gray-600 mb-2">Plan before executing:</p>
                <pre className="bg-gray-900 text-green-400 p-3 rounded overflow-x-auto text-sm">
{`anvil run --flow plan "Refactor authentication module"`}
                </pre>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="text-sm text-gray-600 mb-2">Interactive chat with plan agent:</p>
                <pre className="bg-gray-900 text-green-400 p-3 rounded overflow-x-auto text-sm">
{`anvil chat --agent plan`}
                </pre>
              </div>
              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="text-sm text-gray-600 mb-2">Verify without making changes:</p>
                <pre className="bg-gray-900 text-green-400 p-3 rounded overflow-x-auto text-sm">
{`anvil verify --checks syntax,lint src/`}
                </pre>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
