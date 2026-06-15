export default function Memory() {
  return (
    <div className="min-h-screen bg-white">
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <h1 className="text-5xl font-bold mb-8">Agent Memory</h1>
        
        <div className="prose prose-lg max-w-none">
          <section className="mb-12">
            <p className="text-xl text-gray-600 mb-6">
              Anvil has persistent memory across sessions. It learns from your interactions and 
              applies that knowledge to future tasks.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Memory Categories</h2>
            <div className="grid md:grid-cols-2 gap-4 my-6">
              <div className="bg-purple-50 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Preference</h3>
                <p className="text-sm text-gray-600">
                  Your coding style, tool preferences, and workflow choices
                </p>
              </div>
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Project</h3>
                <p className="text-sm text-gray-600">
                  Project-specific context, tech stack, and conventions
                </p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Pattern</h3>
                <p className="text-sm text-gray-600">
                  Successful approaches and solutions that worked well
                </p>
              </div>
              <div className="bg-red-50 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Mistake</h3>
                <p className="text-sm text-gray-600">
                  Things to avoid based on past failures
                </p>
              </div>
              <div className="bg-yellow-50 p-4 rounded-lg">
                <h3 className="font-semibold mb-2">Fact</h3>
                <p className="text-sm text-gray-600">
                  General knowledge and facts learned during tasks
                </p>
              </div>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">How Memory Works</h2>
            <div className="bg-gray-50 p-6 rounded-lg my-6">
              <h3 className="text-xl font-semibold mb-3">Automatic Extraction</h3>
              <p className="text-gray-600 mb-4">
                After each task, Anvil automatically extracts relevant memories:
              </p>
              <ul className="list-disc list-inside text-gray-600 space-y-2">
                <li>Project context from task descriptions</li>
                <li>Successful patterns from completed tasks</li>
                <li>Mistakes to avoid from failed tasks</li>
                <li>User preferences from interactions</li>
              </ul>
            </div>

            <div className="bg-gray-50 p-6 rounded-lg my-6">
              <h3 className="text-xl font-semibold mb-3">Context Injection</h3>
              <p className="text-gray-600 mb-4">
                Before each task, Anvil recalls relevant memories and injects them into the system prompt:
              </p>
              <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto">
{`Relevant memories from past interactions:
- [Preference] User prefers TypeScript over JavaScript
- [Project] Working on React TypeScript project
- [Pattern] Use functional components in React`}
              </pre>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Memory Management</h2>
            
            <h3 className="text-xl font-semibold mb-3">List Memories</h3>
            <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto mb-4">
{`# List all memories
anvil memory list

# Filter by category
anvil memory list --category preference

# Limit results
anvil memory list --limit 20`}
            </pre>

            <h3 className="text-xl font-semibold mb-3">Add Memories</h3>
            <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto mb-4">
{`anvil memory add \\
  --category preference \\
  --content "User prefers TypeScript over JavaScript" \\
  --context "React project setup" \\
  --importance 0.8`}
            </pre>

            <h3 className="text-xl font-semibold mb-3">Recall Memories</h3>
            <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto mb-4">
{`# Recall memories for a query
anvil memory recall "React TypeScript"

# Limit results
anvil memory recall "React" --limit 5`}
            </pre>

            <h3 className="text-xl font-semibold mb-3">Delete Memories</h3>
            <pre className="bg-gray-900 text-green-400 p-4 rounded overflow-x-auto mb-4">
{`# Delete a specific memory
anvil memory delete mem_abc123

# Clear all memories
anvil memory clear

# Clear by category
anvil memory clear --category mistake`}
            </pre>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Memory Storage</h2>
            <p className="text-gray-600 mb-4">
              Memories are stored locally in <code className="bg-gray-200 px-2 py-1 rounded">~/.anvil/memory/memories.json</code>
            </p>
            <div className="bg-gray-50 p-4 rounded-lg">
              <pre className="text-sm text-gray-700 overflow-x-auto">
{`{
  "memories": [
    {
      "id": "mem_abc123",
      "category": "preference",
      "content": "User prefers TypeScript over JavaScript",
      "context": "React project setup",
      "importance": 0.8,
      "use_count": 5,
      "created_at": "2026-06-15T10:00:00Z",
      "last_used": "2026-06-15T12:00:00Z"
    }
  ]
}`}
              </pre>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-3xl font-semibold mb-4">Best Practices</h2>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>Let Anvil automatically extract memories from tasks</li>
              <li>Manually add important preferences and patterns</li>
              <li>Regularly review and clean up outdated memories</li>
              <li>Use importance scores to prioritize critical memories</li>
              <li>Clear mistake memories once you've learned from them</li>
            </ul>
          </section>

          <section>
            <h2 className="text-3xl font-semibold mb-4">Next Steps</h2>
            <ul className="list-disc list-inside text-gray-600 space-y-2">
              <li>
                <a href="/docs/skills" className="text-purple-600 hover:text-purple-700">
                  Skills Documentation →
                </a>
              </li>
              <li>
                <a href="/docs/cli" className="text-purple-600 hover:text-purple-700">
                  CLI Reference →
                </a>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
