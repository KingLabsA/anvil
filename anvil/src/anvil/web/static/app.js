// Anvil — Full Agent Web UI
// Wires up: Run pipeline, Codebase, Git, MCP, Memory, Sessions, Docs, Metrics, Subagents, Checkpoints, Plan/Act, File Explorer, Diff Viewer, Streaming

class AnvilApp {
  constructor() {
    this.theme = localStorage.getItem('anvil-theme') || 'dark';
    this.currentModel = '';
    this.currentAgent = 'build';
    this.settings = {};
    this.ollamaModels = [];
    this.planMode = 'plan'; // plan or act
    this.currentPath = '.';
    this.ws = null;
    this.init();
  }

  async init() {
    this.applyTheme();
    this.initEvents();
    await this.loadSettings();
    await this.loadModels();
    await this.loadMCPSessions();
    await this.loadPlanMode();
    await this.loadCheckpoints();
    this.setStatus('Ready', 'ready');
  }

  applyTheme() {
    document.documentElement.setAttribute('data-theme', this.theme);
    const icon = document.querySelector('#theme-toggle i');
    if (icon) icon.className = this.theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
  }

  async loadSettings() {
    try {
      const res = await fetch('/settings');
      this.settings = await res.json();
    } catch (e) {}
  }

  async loadModels() {
    const select = document.querySelector('#model-select');
    try {
      const ollamaRes = await fetch('/ollama/models');
      this.ollamaModels = await ollamaRes.json();
      const res = await fetch('/models');
      const providers = await res.json();

      let html = '';
      if (this.ollamaModels.length > 0) {
        html += '<optgroup label="Ollama (Local)">';
        this.ollamaModels.forEach(m => {
          const s = (m.size_gb || 0) + 'GB';
          html += `<option value="${m.name}">${m.name} (${s})</option>`;
        });
        html += '</optgroup>';
        this.currentModel = this.ollamaModels[0].name;
      }

      const grouped = {};
      providers.filter(p => p.provider !== 'ollama').forEach(p => {
        if (!grouped[p.provider]) grouped[p.provider] = [];
        grouped[p.provider].push(p);
      });
      Object.keys(grouped).forEach(prov => {
        html += `<optgroup label="${prov}">`;
        grouped[prov].forEach(p => html += `<option value="${p.model}">${p.display_name || p.model}</option>`);
        html += '</optgroup>';
      });

      select.innerHTML = html || '<option>No models</option>';
      this.updateModelDisplay();
      this.populateSidebarModels();
    } catch (e) {
      select.innerHTML = '<option>Error</option>';
    }
  }

  populateSidebarModels() {
    const list = document.querySelector('#models-list');
    if (!list) return;
    list.innerHTML = this.ollamaModels.map(m =>
      `<div class="nav-item" onclick="app.selectModel('${m.name}')"><span class="dot" style="background:var(--green)"></span><span>${m.name}</span><span class="badge">${m.size_gb}GB</span></div>`
    ).join('');
  }

  async loadMCPSessions() {
    // MCP tools
    const toolsList = document.querySelector('#mcp-tools-list');
    if (toolsList) {
      try {
        const res = await fetch('/mcp/tools');
        const tools = await res.json();
        toolsList.innerHTML = tools.map(t =>
          `<div class="nav-item"><i class="fas fa-wrench" style="font-size:0.7rem;color:var(--purple)"></i><span>${t.name}</span></div>`
        ).join('');
      } catch (e) {}
    }

    // Sessions
    const sessList = document.querySelector('#sessions-list');
    if (sessList) {
      try {
        const res = await fetch('/sessions');
        const sessions = await res.json();
        sessList.innerHTML = sessions.length === 0
          ? '<div class="nav-item" style="color:var(--text-tertiary)">No sessions</div>'
          : sessions.slice(-8).reverse().map(s =>
            `<div class="nav-item"><i class="fas fa-terminal" style="font-size:0.7rem;color:var(--text-tertiary)"></i><span>${(s.task||'').slice(0,25)}</span><span class="badge">${s.steps||0}</span></div>`
          ).join('');
      } catch (e) {}
    }
  }

  initEvents() {
    const input = document.querySelector('#task-input');
    if (input) {
      input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 120) + 'px'; });
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); this.runTask(); }
      });
    }

    document.querySelector('#run-btn')?.addEventListener('click', () => this.runTask());
    document.querySelector('#task-run')?.addEventListener('click', () => this.runTask());
    document.querySelector('#settings-btn')?.addEventListener('click', () => this.showSettings());
    document.querySelector('#theme-toggle')?.addEventListener('click', () => { this.theme = this.theme === 'dark' ? 'light' : 'dark'; localStorage.setItem('anvil-theme', this.theme); this.applyTheme(); });

    document.querySelector('#model-select')?.addEventListener('change', (e) => { this.currentModel = e.target.value; this.updateModelDisplay(); });
    document.querySelector('#agent-select')?.addEventListener('change', (e) => { this.currentAgent = e.target.value; document.querySelector('#current-agent').textContent = e.target.selectedOptions[0].text; this.highlightAgent(); });

    // Tabs
    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => { p.style.display = 'none'; p.classList.remove('active'); });
        tab.classList.add('active');
        const panel = document.querySelector(`#panel-${tab.dataset.tab}`);
        if (panel) { panel.style.display = 'flex'; panel.classList.add('active'); }
      });
    });

    // Sidebar agent click
    document.querySelectorAll('#agents-list .nav-item').forEach(el => {
      el.addEventListener('click', () => {
        this.currentAgent = el.dataset.agent;
        document.querySelector('#agent-select').value = this.currentAgent;
        this.highlightAgent();
      });
    });

    // Codebase search
    document.querySelector('#codebase-search')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.searchCodebase();
    });
    document.querySelector('#docs-search')?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.searchDocs();
    });
  }

  highlightAgent() {
    document.querySelectorAll('#agents-list .nav-item').forEach(el => {
      el.classList.toggle('active', el.dataset.agent === this.currentAgent);
    });
    document.querySelector('#current-agent').textContent = this.currentAgent;
  }

  selectModel(name) {
    this.currentModel = name;
    document.querySelector('#model-select').value = name;
    this.updateModelDisplay();
  }

  updateModelDisplay() {
    document.querySelector('#current-model').textContent = this.currentModel || '-';
  }

  setTask(text) {
    const input = document.querySelector('#task-input');
    if (input) { input.value = text; input.focus(); input.dispatchEvent(new Event('input')); }
    document.querySelector('.welcome-full')?.remove();
  }

  async runTask() {
    const input = document.querySelector('#task-input');
    if (!input || !input.value.trim()) return;

    const task = input.value.trim();
    input.value = '';
    input.style.height = 'auto';
    document.querySelector('.welcome-full')?.remove();

    // Show pipeline
    const pipe = document.querySelector('#pipeline-status');
    if (pipe) pipe.style.display = 'flex';
    this.animatePipeline('plan');

    this.logEntry('info', `Starting task: ${task}`);
    this.logEntry('info', `Agent: ${this.currentAgent} | Model: ${this.currentModel}`);
    this.setStatus('Running...', 'active');

    const startTime = Date.now();

    try {
      const res = await fetch('/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: task,
          model: this.currentModel || 'shellwhisperer',
          max_iterations: 20,
          verify: true,
        }),
      });

      const data = await res.json();
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

      this.animatePipeline('done');

      if (data.success) {
        this.logEntry('success', `Task completed in ${data.steps} steps (${elapsed}s)`);
        if (data.output) this.logEntry('output', data.output);
        this.setStatus('Completed', 'ready');
      } else {
        this.logEntry('error', `Task failed: ${data.error}`);
        this.setStatus('Error', 'error');
      }

      document.querySelector('#response-time').textContent = `${elapsed}s`;
      this.loadMCPSessions();
    } catch (e) {
      this.logEntry('error', `Error: ${e.message}`);
      this.setStatus('Error', 'error');
      this.animatePipeline('error');
    }
  }

  animatePipeline(state) {
    const steps = document.querySelectorAll('.pipeline-step');
    if (state === 'plan') {
      steps.forEach((s, i) => { s.className = 'pipeline-step'; if (i === 0) s.classList.add('active'); });
    } else if (state === 'done') {
      steps.forEach(s => { s.className = 'pipeline-step done'; });
    } else if (state === 'error') {
      steps.forEach(s => { if (s.classList.contains('active')) s.classList.add('error'); });
    } else {
      const arr = Array.from(steps);
      const activeIdx = arr.findIndex(s => s.classList.contains('active'));
      if (activeIdx >= 0 && activeIdx < arr.length - 1) {
        arr[activeIdx].classList.remove('active');
        arr[activeIdx].classList.add('done');
        arr[activeIdx + 1].classList.add('active');
      }
    }
  }

  logEntry(type, msg) {
    const log = document.querySelector('#output-log');
    if (!log) return '';
    const cls = type === 'success' ? 'log-success' : type === 'error' ? 'log-error' : type === 'warning' ? 'log-warning' : 'log-info';
    const time = new Date().toLocaleTimeString();
    const id = 'log-' + Date.now() + '-' + Math.random().toString(36).slice(2,6);
    log.innerHTML += `<div class="log-entry" id="${id}"><span class="log-info">[${time}]</span> <span class="${cls}">${this.escape(msg)}</span></div>`;
    log.scrollTop = log.scrollHeight;
    return id;
  }

  clearOutput() {
    const log = document.querySelector('#output-log');
    if (log) log.innerHTML = '';
  }

  copyOutput() {
    const log = document.querySelector('#output-log');
    if (log) navigator.clipboard.writeText(log.innerText);
  }

  removeMessage(id) {
    if (id) {
      const el = document.querySelector(`#${id}`);
      if (el) el.remove();
    }
  }

  // ─── Codebase ───
  async indexCodebase() {
    const results = document.querySelector('#codebase-results');
    results.innerHTML = '<div class="empty-state"><div class="thinking"><span></span><span></span><span></span></div><p>Indexing codebase...</p></div>';
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'List the key files and modules in this codebase', model: this.currentModel }),
      });
      const data = await res.json();
      results.innerHTML = `<div class="log-entry"><span class="log-msg" style="white-space:pre-wrap">${this.escape(data.response)}</span></div>`;
    } catch (e) {
      results.innerHTML = `<div class="empty-state"><p>Error: ${e.message}</p></div>`;
    }
  }

  async searchCodebase() {
    const q = document.querySelector('#codebase-search').value;
    if (!q) return;
    const results = document.querySelector('#codebase-results');
    results.innerHTML = '<div class="empty-state"><div class="thinking"><span></span><span></span><span></span></div></div>';
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `Search the codebase for: ${q}. Show file paths and relevant code snippets.`, model: this.currentModel }),
      });
      const data = await res.json();
      results.innerHTML = `<div class="log-entry"><span class="log-msg" style="white-space:pre-wrap">${this.escape(data.response)}</span></div>`;
    } catch (e) {}
  }

  // ─── Git ───
  async gitStatus() {
    const out = document.querySelector('#git-output');
    out.innerHTML = '<div class="empty-state"><div class="thinking"><span></span><span></span><span></span></div></div>';
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'Run git status and show the results', model: this.currentModel }),
      });
      const data = await res.json();
      out.innerHTML = `<div class="log-entry"><span class="log-msg" style="white-space:pre-wrap;font-family:var(--font-mono)">${this.escape(data.response)}</span></div>`;
    } catch (e) {}
  }

  async gitDiff() {
    const out = document.querySelector('#git-output');
    out.innerHTML = '<div class="empty-state"><div class="thinking"><span></span><span></span><span></span></div></div>';
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'Run git diff and show the results', model: this.currentModel }),
      });
      const data = await res.json();
      out.innerHTML = `<div class="log-entry"><span class="log-msg" style="white-space:pre-wrap;font-family:var(--font-mono)">${this.escape(data.response)}</span></div>`;
    } catch (e) {}
  }

  // ─── Sessions ───
  async loadSessions() {
    const out = document.querySelector('#sessions-output');
    try {
      const res = await fetch('/sessions');
      const sessions = await res.json();
      if (sessions.length === 0) {
        out.innerHTML = '<div class="empty-state"><i class="fas fa-history"></i><p>No sessions yet</p></div>';
        return;
      }
      out.innerHTML = sessions.map(s =>
        `<div class="log-entry"><span class="log-info">[${s.created_at || ''}]</span> <span class="log-msg">${this.escape(s.task)}</span> <span class="log-step">${s.steps} steps</span></div>`
      ).join('');
    } catch (e) {}
  }

  // ─── Docs RAG ───
  async searchDocs() {
    const q = document.querySelector('#docs-search').value;
    if (!q) return;
    const out = document.querySelector('#docs-output');
    out.innerHTML = '<div class="empty-state"><div class="thinking"><span></span><span></span><span></span></div></div>';
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: `Search documentation for: ${q}. Show relevant docs and code examples.`, model: this.currentModel }),
      });
      const data = await res.json();
      out.innerHTML = `<div class="log-entry"><span class="log-msg" style="white-space:pre-wrap">${this.escape(data.response)}</span></div>`;
    } catch (e) {}
  }

  // ─── Metrics ───
  async loadMetrics() {
    try {
      const res = await fetch('/sessions');
      const sessions = await res.json();
      document.querySelector('#metric-sessions').textContent = sessions.length;
      document.querySelector('#metric-steps').textContent = sessions.reduce((a, s) => a + (s.steps || 0), 0);
      document.querySelector('#metric-errors').textContent = sessions.length ? Math.round(sessions.filter(s => !s.success).length / sessions.length * 100) + '%' : '0%';
      document.querySelector('#metric-recovery').textContent = '100%';
    } catch (e) {}
  }

  // ─── Settings ───
  showSettings() {
    const modal = document.querySelector('#settings-modal');
    if (!modal) return;
    const fields = { 'openai-api-key': 'openai_api_key', 'anthropic-api-key': 'anthropic_api_key', 'gemini-api-key': 'gemini_api_key', 'deepseek-api-key': 'deepseek_api_key' };
    Object.entries(fields).forEach(([id, key]) => {
      const el = document.querySelector(`#${id}`);
      if (el) el.value = this.settings[key] || '';
    });
    const dm = document.querySelector('#default-model');
    if (dm) {
      let opts = this.ollamaModels.map(m => `<option value="${m.name}">${m.name} (Local)</option>`).join('');
      opts += '<option value="gpt-4o">GPT-4o</option><option value="claude-3.5-sonnet">Claude 3.5 Sonnet</option>';
      dm.innerHTML = opts;
      dm.value = this.settings.default_model || this.currentModel;
    }
    modal.style.display = 'flex';
  }

  closeSettings() { document.querySelector('#settings-modal').style.display = 'none'; }

  async saveSettings() {
    const modal = document.querySelector('#settings-modal');
    const newSettings = {
      openai_api_key: modal.querySelector('#openai-api-key')?.value || null,
      anthropic_api_key: modal.querySelector('#anthropic-api-key')?.value || null,
      gemini_api_key: modal.querySelector('#gemini-api-key')?.value || null,
      deepseek_api_key: modal.querySelector('#deepseek-api-key')?.value || null,
      default_model: modal.querySelector('#default-model')?.value || this.currentModel,
      workspace: this.settings.workspace || '.',
    };
    try {
      await fetch('/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newSettings) });
      this.settings = newSettings;
      this.currentModel = newSettings.default_model;
      this.updateModelDisplay();
      this.closeSettings();
      this.notify('Settings saved', 'success');
    } catch (e) { this.notify('Failed to save', 'error'); }
  }

  setStatus(text, state) {
    const dot = document.querySelector('#status-dot');
    const label = document.querySelector('#status-text');
    if (label) label.textContent = text;
    if (dot) { dot.className = 'status-dot'; if (state === 'error') dot.classList.add('error'); else if (state === 'active') dot.classList.add('active'); }
  }

  notify(message, type) {
    const container = document.querySelector('#notification-container');
    if (!container) return;
    const icons = { success: 'check-circle', error: 'exclamation-circle', info: 'info-circle' };
    const notif = document.createElement('div');
    notif.className = `notification ${type}`;
    notif.innerHTML = `<i class="fas fa-${icons[type] || 'info-circle'}"></i><span>${message}</span>`;
    container.appendChild(notif);
    setTimeout(() => { notif.classList.add('fade-out'); setTimeout(() => notif.remove(), 300); }, 3000);
  }

  escape(text) { const d = document.createElement('div'); d.textContent = text; return d.innerHTML; }

  // ─── File Explorer ───
  async loadFileTree(path = '.') {
    const results = document.querySelector('#file-explorer-results');
    if (!results) return;
    results.innerHTML = '<div class="empty-state"><div class="thinking"><span></span><span></span><span></span></div></div>';
    try {
      const res = await fetch(`/files/tree?path=${encodeURIComponent(path)}&max_depth=3`);
      const tree = await res.json();
      results.innerHTML = this.renderTree(tree, 0);
    } catch (e) {
      results.innerHTML = `<div class="empty-state"><p>Error: ${e.message}</p></div>`;
    }
  }

  renderTree(node, depth) {
    const indent = depth * 16;
    let html = '';
    if (node.type === 'directory') {
      html += `<div class="tree-item dir" style="padding-left:${indent}px" onclick="this.classList.toggle('open')">
        <i class="fas fa-folder" style="color:var(--orange)"></i> ${this.escape(node.name)}
      </div>`;
      if (node.children) {
        html += `<div class="tree-children">`;
        node.children.forEach(c => { html += this.renderTree(c, depth + 1); });
        html += `</div>`;
      }
    } else {
      const icon = this.getFileIcon(node.name);
      html += `<div class="tree-item file" style="padding-left:${indent}px" onclick="app.openFile('${this.escape(node.name)}')">
        <i class="${icon}"></i> ${this.escape(node.name)}
        <span class="badge">${this.formatSize(node.size || 0)}</span>
      </div>`;
    }
    return html;
  }

  getFileIcon(name) {
    if (name.endsWith('.py')) return 'fab fa-python';
    if (name.endsWith('.js') || name.endsWith('.ts') || name.endsWith('.tsx')) return 'fab fa-js';
    if (name.endsWith('.rs')) return 'fab fa-rust';
    if (name.endsWith('.go')) return 'fab fa-go';
    if (name.endsWith('.md')) return 'fab fa-markdown';
    if (name.endsWith('.json')) return 'fas fa-code';
    if (name.endsWith('.yml') || name.endsWith('.yaml')) return 'fas fa-cog';
    return 'fas fa-file';
  }

  formatSize(bytes) {
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + 'KB';
    return (bytes/1024/1024).toFixed(1) + 'MB';
  }

  async openFile(path) {
    try {
      const res = await fetch(`/files/read?path=${encodeURIComponent(path)}`);
      const data = await res.json();
      if (data.error) return this.notify(data.error, 'error');
      this.logEntry('info', `📄 ${data.path} (${data.lines} lines)`);
      this.logEntry('output', data.content);
    } catch (e) {}
  }

  // ─── Checkpoints ───
  async loadCheckpoints() {
    try {
      const res = await fetch('/checkpoint/list');
      const checkpoints = await res.json();
      const el = document.querySelector('#checkpoint-list');
      if (el) {
        el.innerHTML = checkpoints.length === 0
          ? '<div class="nav-item" style="color:var(--text-tertiary)">No checkpoints</div>'
          : checkpoints.slice(-10).reverse().map(c =>
            `<div class="nav-item ${c.is_current ? 'active' : ''}">
              <i class="fas fa-bookmark" style="font-size:0.7rem;color:var(--accent)"></i>
              <span>${c.message.slice(0,25)}</span>
            </div>`
          ).join('');
      }
    } catch (e) {}
  }

  async createCheckpoint(msg) {
    try {
      const res = await fetch(`/checkpoint/create?message=${encodeURIComponent(msg)}`, { method: 'POST' });
      const data = await res.json();
      this.notify(`Checkpoint created: ${data.hash?.slice(0,7)}`, 'success');
      this.loadCheckpoints();
    } catch (e) { this.notify('Checkpoint failed', 'error'); }
  }

  async undoCheckpoint() {
    try {
      const res = await fetch('/checkpoint/undo', { method: 'POST' });
      const data = await res.json();
      if (data.error) return this.notify(data.error, 'info');
      this.notify(`Undone to ${data.hash?.slice(0,7)}`, 'success');
      this.loadCheckpoints();
    } catch (e) {}
  }

  async redoCheckpoint() {
    try {
      const res = await fetch('/checkpoint/redo', { method: 'POST' });
      const data = await res.json();
      if (data.error) return this.notify(data.error, 'info');
      this.notify(`Redone to ${data.hash?.slice(0,7)}`, 'success');
      this.loadCheckpoints();
    } catch (e) {}
  }

  async showDiff(checkpointId) {
    const out = document.querySelector('#git-output');
    if (!out) return;
    try {
      const res = await fetch(`/checkpoint/diff/${checkpointId}`);
      const diff = await res.text();
      out.innerHTML = `<pre class="diff-view">${this.escape(diff)}</pre>`;
    } catch (e) {}
  }

  // ─── Plan/Act Mode ───
  async loadPlanMode() {
    try {
      const res = await fetch('/plan/mode');
      const data = await res.json();
      this.planMode = data.mode;
      this.updatePlanModeUI();
    } catch (e) {}
  }

  async togglePlanMode() {
    const newMode = this.planMode === 'plan' ? 'act' : 'plan';
    try {
      await fetch(`/plan/mode/${newMode}`, { method: 'POST' });
      this.planMode = newMode;
      this.updatePlanModeUI();
      this.notify(`Switched to ${newMode.toUpperCase()} mode`, 'info');
    } catch (e) {}
  }

  updatePlanModeUI() {
    const btn = document.querySelector('#plan-mode-btn');
    if (btn) {
      btn.textContent = this.planMode === 'plan' ? '📋 Plan' : '⚡ Act';
      btn.className = this.planMode === 'plan' ? 'mode-btn plan' : 'mode-btn act';
    }
  }

  async createPlan(task, steps) {
    try {
      const res = await fetch('/plan/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, steps }),
      });
      const data = await res.json();
      this.notify(`Plan created with ${data.steps} steps`, 'success');
      this.showPlan();
    } catch (e) {}
  }

  async approvePlan() {
    try {
      const res = await fetch('/plan/approve', { method: 'POST' });
      const data = await res.json();
      this.notify(data.message, 'success');
      this.planMode = data.mode;
      this.updatePlanModeUI();
    } catch (e) {}
  }

  async showPlan() {
    try {
      const res = await fetch('/plan/current');
      const plan = await res.json();
      if (!plan.task) return this.logEntry('info', 'No active plan');
      this.logEntry('info', `📋 Plan: ${plan.task}`);
      (plan.steps || []).forEach(s => {
        const icon = s.status === 'done' ? '✅' : '⏳';
        this.logEntry('info', `  ${icon} Step ${s.index+1}: ${s.description}`);
      });
    } catch (e) {}
  }

  // ─── Subagents ───
  async spawnSubagent(task, agent = 'general') {
    try {
      const res = await fetch(`/subagent/spawn?task=${encodeURIComponent(task)}&agent=${agent}&model=${this.currentModel}`, { method: 'POST' });
      const data = await res.json();
      this.logEntry('info', `🤖 Spawned subagent: ${data.task_id}`);
      // Execute it
      const execRes = await fetch(`/subagent/execute/${data.task_id}`, { method: 'POST' });
      const result = await execRes.json();
      this.logEntry(result.status === 'completed' ? 'success' : 'error', `Subagent result: ${result.output?.slice(0, 500)}`);
    } catch (e) { this.notify('Subagent failed', 'error'); }
  }

  async loadSubagentHistory() {
    try {
      const res = await fetch('/subagent/history');
      const history = await res.json();
      return history;
    } catch (e) { return []; }
  }

  // ─── Streaming (WebSocket) ───
  connectWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.ws = new WebSocket(`${proto}//${location.host}/ws/chat`);
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'thinking') {
        this.setStatus('Thinking...', 'active');
        this._thinkingId = this.logEntry('info', '🤔 Thinking...');
      } else if (data.type === 'response') {
        if (data.success) {
          this.logEntry('success', data.response || '(empty response)');
          this.setStatus('Ready', 'ready');
        } else {
          this.logEntry('error', `Error: ${data.error}`);
          this.setStatus('Error', 'error');
        }
      }
    };
    this.ws.onclose = () => { setTimeout(() => this.connectWebSocket(), 3000); };
  }

  sendViaWebSocket(message) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.connectWebSocket();
      return false;
    }
    this.ws.send(JSON.stringify({ message, model: this.currentModel }));
    return true;
  }
}

const app = new AnvilApp();
