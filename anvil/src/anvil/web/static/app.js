(() => {
  'use strict';

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];
  const debounce = (fn, ms = 200) => {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  };

  class AnvilApp {
    constructor() {
      this.theme = localStorage.getItem('anvil-theme') || 'dark';
      this.history = [];
      this.historyIndex = -1;
      this.debugSession = null;
      this.breakpoints = [];
      this.multiFileEdits = [];

      this.applyTheme();
      this.initCommandPalette();
      this.initKeyboardShortcuts();
      this.initUndoRedo();
      this.initDragDrop();
      this.initMultiFileEdit();
      this.initDebugging();
      this.initSidebar();
      this.initEditorTabs();
      this.initTextarea();
      this.initStatusDot();
    }

    // ─── Theme ───────────────────────────────────────────────────────────────
    applyTheme() {
      document.documentElement.setAttribute('data-theme', this.theme);
      const icon = $('#theme-toggle i');
      if (icon) icon.className = this.theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
    }

    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('anvil-theme', this.theme);
      this.applyTheme();
    }

    // ─── Command Palette ─────────────────────────────────────────────────────
    initCommandPalette() {
      const overlay = $('#command-palette');
      const input = $('#command-input');
      const results = $('#command-results');
      if (!overlay || !input || !results) return;

      const globalSearch = $('#global-search');
      if (globalSearch) {
        globalSearch.addEventListener('focus', () => this.showCommandPalette());
      }

      input.addEventListener('input', debounce(e => this.filterCommands(e.target.value), 80));

      input.addEventListener('keydown', e => {
        const items = $$('.command-item', results);
        const selected = $('.command-item.selected', results);
        const idx = items.indexOf(selected);

        if (e.key === 'ArrowDown') {
          e.preventDefault();
          const next = items[(idx + 1) % items.length];
          if (next) {
            selected?.classList.remove('selected');
            next.classList.add('selected');
            next.scrollIntoView({ block: 'nearest' });
          }
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          const prev = items[(idx - 1 + items.length) % items.length];
          if (prev) {
            selected?.classList.remove('selected');
            prev.classList.add('selected');
            prev.scrollIntoView({ block: 'nearest' });
          }
        } else if (e.key === 'Enter') {
          e.preventDefault();
          if (selected) this.executeCommand(selected.dataset.command);
        } else if (e.key === 'Escape') {
          this.hideCommandPalette();
        }
      });

      overlay.addEventListener('click', e => {
        if (e.target === overlay) this.hideCommandPalette();
      });
    }

    toggleCommandPalette() {
      $('#command-palette').classList.contains('visible')
        ? this.hideCommandPalette()
        : this.showCommandPalette();
    }

    showCommandPalette() {
      const overlay = $('#command-palette');
      const input = $('#command-input');
      overlay.classList.add('visible');
      input.value = '';
      input.focus();
      this.filterCommands('');
    }

    hideCommandPalette() {
      $('#command-palette').classList.remove('visible');
    }

    filterCommands(query) {
      const results = $('#command-results');
      const q = query.toLowerCase().trim();
      const commands = this.getCommands().filter(cmd =>
        !q || cmd.name.toLowerCase().includes(q) || cmd.description.toLowerCase().includes(q)
      );

      results.innerHTML = commands.map((cmd, i) => `
        <div class="command-item ${i === 0 ? 'selected' : ''}" data-command="${cmd.action}">
          <div class="command-item-icon"><i class="${cmd.icon || 'fas fa-terminal'}"></i></div>
          <div class="command-item-text">
            <div class="command-item-name">${cmd.name}</div>
            <div class="command-item-desc">${cmd.description}</div>
          </div>
          ${cmd.shortcut ? `<span class="command-item-kbd">${cmd.shortcut}</span>` : ''}
        </div>
      `).join('');

      $$('.command-item', results).forEach(item => {
        item.addEventListener('click', () => this.executeCommand(item.dataset.command));
        item.addEventListener('mouseenter', () => {
          $('.command-item.selected', results)?.classList.remove('selected');
          item.classList.add('selected');
        });
      });
    }

    getCommands() {
      return [
        { name: 'Toggle Theme', description: 'Switch between dark and light mode', action: 'toggleTheme', icon: 'fas fa-palette', shortcut: '⌘T' },
        { name: 'New Task', description: 'Create a new task', action: 'newTask', icon: 'fas fa-plus', shortcut: '⌘N' },
        { name: 'Run Task', description: 'Run the current task', action: 'runTask', icon: 'fas fa-play', shortcut: '⌘↵' },
        { name: 'Analyze Code', description: 'Analyze code for issues', action: 'analyzeCode', icon: 'fas fa-search' },
        { name: 'Explain Code', description: 'Explain selected code', action: 'explainCode', icon: 'fas fa-lightbulb' },
        { name: 'Optimize Code', description: 'Optimize for performance', action: 'optimizeCode', icon: 'fas fa-bolt' },
        { name: 'Review Code', description: 'Review for best practices', action: 'reviewCode', icon: 'fas fa-code' },
        { name: 'Fix Issues', description: 'Auto-fix detected issues', action: 'fixIssues', icon: 'fas fa-wrench' },
        { name: 'Generate Tests', description: 'Generate unit tests', action: 'generateTests', icon: 'fas fa-vial' },
        { name: 'Multi-File Edit', description: 'Edit multiple files at once', action: 'multiFileEdit', icon: 'fas fa-layer-group' },
        { name: 'Debug', description: 'Open debugger panel', action: 'openDebug', icon: 'fas fa-bug' },
        { name: 'Clear Output', description: 'Clear the output panel', action: 'clearOutput', icon: 'fas fa-trash' },
        { name: 'Copy Output', description: 'Copy response to clipboard', action: 'copyOutput', icon: 'fas fa-copy', shortcut: '⌘⇧C' },
        { name: 'Settings', description: 'Open settings', action: 'openSettings', icon: 'fas fa-cog' },
      ];
    }

    executeCommand(action) {
      this.hideCommandPalette();
      const actions = {
        toggleTheme: () => this.toggleTheme(),
        newTask: () => { const q = $('#query'); if (q) { q.value = ''; q.focus(); } },
        runTask: () => $('#submit')?.click(),
        analyzeCode: () => this.quickAction('analyze'),
        explainCode: () => this.quickAction('explain'),
        optimizeCode: () => this.quickAction('optimize'),
        reviewCode: () => this.quickAction('review'),
        fixIssues: () => this.quickAction('fix'),
        generateTests: () => this.quickAction('generateTests'),
        multiFileEdit: () => this.showMultiFileEdit(),
        openDebug: () => this.showDebugPanel(),
        clearOutput: () => { const r = $('#response'); if (r) r.style.display = 'none'; },
        copyOutput: () => this.copyOutput(),
        openSettings: () => this.showNotification('Settings coming soon', 'info'),
      };
      actions[action]?.();
    }

    // ─── Keyboard Shortcuts ──────────────────────────────────────────────────
    initKeyboardShortcuts() {
      document.addEventListener('keydown', e => {
        const mod = e.metaKey || e.ctrlKey;

        if (mod && e.key === 'k') {
          e.preventDefault();
          this.toggleCommandPalette();
        } else if (mod && e.key === 'Enter') {
          e.preventDefault();
          $('#submit')?.click();
        } else if (mod && e.key === '/') {
          e.preventDefault();
          $('#query')?.focus();
        } else if (mod && e.shiftKey && e.key === 'C') {
          e.preventDefault();
          this.copyOutput();
        } else if (mod && e.key === 'z' && !e.shiftKey) {
          if (document.activeElement?.tagName !== 'TEXTAREA') {
            e.preventDefault();
            this.undo();
          }
        } else if (mod && e.shiftKey && e.key === 'Z') {
          if (document.activeElement?.tagName !== 'TEXTAREA') {
            e.preventDefault();
            this.redo();
          }
        } else if (e.key === 'Escape') {
          this.hideCommandPalette();
        }
      });
    }

    // ─── Undo / Redo ─────────────────────────────────────────────────────────
    initUndoRedo() {
      const query = $('#query');
      if (!query) return;
      query.addEventListener('input', () => this.addToHistory(query.value));
    }

    addToHistory(value) {
      if (this.historyIndex < this.history.length - 1) {
        this.history = this.history.slice(0, this.historyIndex + 1);
      }
      this.history.push(value);
      this.historyIndex = this.history.length - 1;
      if (this.history.length > 100) {
        this.history.shift();
        this.historyIndex--;
      }
    }

    undo() {
      if (this.historyIndex > 0) {
        this.historyIndex--;
        const q = $('#query');
        if (q) q.value = this.history[this.historyIndex];
      }
    }

    redo() {
      if (this.historyIndex < this.history.length - 1) {
        this.historyIndex++;
        const q = $('#query');
        if (q) q.value = this.history[this.historyIndex];
      }
    }

    // ─── Drag & Drop ─────────────────────────────────────────────────────────
    initDragDrop() {
      const dropZone = $('#drop-zone');
      const overlay = $('#drop-overlay');
      if (!dropZone || !overlay) return;

      let dragCounter = 0;

      document.addEventListener('dragenter', e => {
        e.preventDefault();
        dragCounter++;
        overlay.classList.add('visible');
      });

      document.addEventListener('dragleave', e => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter <= 0) {
          dragCounter = 0;
          overlay.classList.remove('visible');
        }
      });

      document.addEventListener('dragover', e => e.preventDefault());

      document.addEventListener('drop', e => {
        e.preventDefault();
        dragCounter = 0;
        overlay.classList.remove('visible');
        const files = e.dataTransfer?.files;
        if (files?.length) this.handleFileDrop(files[0]);
      });
    }

    async handleFileDrop(file) {
      const reader = new FileReader();
      reader.onload = e => {
        const q = $('#query');
        if (q) {
          q.value = `Analyze this ${file.name}:\n\n${e.target.result}`;
          q.dispatchEvent(new Event('input'));
        }
      };
      reader.readAsText(file);
    }

    // ─── Quick Actions ───────────────────────────────────────────────────────
    quickAction(action) {
      const prompts = {
        analyze: 'Analyze this code for issues:',
        explain: 'Explain this code in simple terms:',
        optimize: 'Optimize this code for performance and readability:',
        review: 'Review this code for bugs, security issues, and best practices:',
        fix: 'Fix any issues in this code:',
        generateTests: 'Generate comprehensive unit tests for this code:',
      };

      const selection = window.getSelection()?.toString() || '';
      const q = $('#query');
      if (!q) return;

      q.value = selection
        ? `${prompts[action]}\n\n\`\`\`\n${selection}\n\`\`\``
        : prompts[action];
      q.dispatchEvent(new Event('input'));
      q.focus();
    }

    // ─── Copy Output ─────────────────────────────────────────────────────────
    copyOutput() {
      const content = $('#response-content');
      if (!content) return;
      navigator.clipboard.writeText(content.textContent).then(() => {
        this.showNotification('Copied to clipboard', 'success');
      });
    }

    // ─── Multi-File Edit ─────────────────────────────────────────────────────
    initMultiFileEdit() {
      const btn = $('#add-multi-edit');
      if (btn) btn.addEventListener('click', () => this.addMultiFileEdit());
    }

    addMultiFileEdit() {
      const container = $('#multi-edit-container');
      if (!container) return;

      const item = document.createElement('div');
      item.className = 'multi-edit-item';
      item.innerHTML = `
        <div class="multi-edit-row">
          <select class="edit-action">
            <option value="create">Create</option>
            <option value="update">Update</option>
            <option value="delete">Delete</option>
          </select>
          <input type="text" class="edit-path" placeholder="File path (e.g., src/main.py)">
          <textarea class="edit-content" placeholder="File content (for create/update)"></textarea>
          <button class="remove-edit-btn">Remove</button>
        </div>
      `;
      container.appendChild(item);
      this.multiFileEdits.push(item);

      $('.remove-edit-btn', item).addEventListener('click', () => {
        item.remove();
        this.multiFileEdits = this.multiFileEdits.filter(i => i !== item);
      });
    }

    async submitMultiFileEdit() {
      const edits = $$('.multi-edit-item').map(item => {
        const action = $('.edit-action', item).value;
        const path = $('.edit-path', item).value;
        const content = $('.edit-content', item).value;
        return path ? { action, path, ...(action !== 'delete' && { content }) } : null;
      }).filter(Boolean);

      if (!edits.length) {
        this.showNotification('No files to edit', 'error');
        return;
      }

      try {
        const res = await fetch('/api/multi-edit', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.getAuthToken()}`,
          },
          body: JSON.stringify({ edits, description: 'Multi-file edit', auto_verify: true }),
        });
        const result = await res.json();
        if (result.success) {
          this.showNotification(`Edited ${result.files_changed.length} file(s)`, 'success');
          this.multiFileEdits = [];
          $('#multi-edit-container').innerHTML = '';
        } else {
          this.showNotification(`Error: ${result.errors.join(', ')}`, 'error');
        }
      } catch (err) {
        this.showNotification(`Error: ${err.message}`, 'error');
      }
    }

    // ─── Debugging ───────────────────────────────────────────────────────────
    initDebugging() {
      const bindings = {
        'start-debug': () => this.startDebugSession(),
        'continue-debug': () => this.continueDebug(),
        'step-over': () => this.stepOver(),
        'step-into': () => this.stepInto(),
        'step-out': () => this.stepOut(),
        'stop-debug': () => this.stopDebugSession(),
      };
      Object.entries(bindings).forEach(([id, fn]) => {
        const el = $(`#${id}`);
        if (el) el.addEventListener('click', fn);
      });
    }

    async debugRequest(url, opts = {}) {
      const res = await fetch(url, {
        ...opts,
        headers: { Authorization: `Bearer ${this.getAuthToken()}`, ...opts.headers },
      });
      return res.json();
    }

    async startDebugSession() {
      const fileInput = $('#debug-file');
      if (!fileInput?.value) {
        this.showNotification('Select a file to debug', 'error');
        return;
      }
      try {
        this.debugSession = await this.debugRequest(
          `/api/debug/start?file=${encodeURIComponent(fileInput.value)}`,
          { method: 'POST' }
        );
        this.showNotification('Debug session started', 'success');
        this.updateDebugUI();
      } catch (err) {
        this.showNotification(`Error: ${err.message}`, 'error');
      }
    }

    async addBreakpoint() {
      if (!this.debugSession) {
        this.showNotification('No active debug session', 'error');
        return;
      }
      const lineInput = $('#breakpoint-line');
      if (!lineInput?.value) {
        this.showNotification('Enter a line number', 'error');
        return;
      }
      try {
        const result = await this.debugRequest('/api/debug/breakpoint', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: this.debugSession.session_id,
            breakpoint: {
              file: this.debugSession.file,
              line: parseInt(lineInput.value),
              condition: $('#breakpoint-condition')?.value || null,
              enabled: true,
            },
          }),
        });
        if (result.success) {
          this.breakpoints.push(result.breakpoint);
          this.showNotification('Breakpoint added', 'success');
          this.updateBreakpointsUI();
        }
      } catch (err) {
        this.showNotification(`Error: ${err.message}`, 'error');
      }
    }

    async continueDebug() {
      if (!this.debugSession) return;
      try {
        const result = await this.debugRequest(
          `/api/debug/continue?session_id=${this.debugSession.session_id}`,
          { method: 'POST' }
        );
        if (result.success) {
          this.debugSession.current_line = result.current_line;
          this.showNotification(`Continued to line ${result.current_line}`, 'success');
          this.updateDebugUI();
        }
      } catch (err) {
        this.showNotification(`Error: ${err.message}`, 'error');
      }
    }

    async stepOver() {
      if (!this.debugSession) return;
      try {
        const result = await this.debugRequest(
          `/api/debug/step-over?session_id=${this.debugSession.session_id}`,
          { method: 'POST' }
        );
        if (result.success) {
          this.debugSession.current_line = result.current_line;
          this.showNotification(`Stepped over to line ${result.current_line}`, 'success');
          this.updateDebugUI();
        }
      } catch (err) {
        this.showNotification(`Error: ${err.message}`, 'error');
      }
    }

    async stepInto() {
      if (!this.debugSession) return;
      try {
        const result = await this.debugRequest(
          `/api/debug/step-into?session_id=${this.debugSession.session_id}`,
          { method: 'POST' }
        );
        if (result.success) {
          this.debugSession.current_line = result.current_line;
          this.showNotification(`Stepped into line ${result.current_line}`, 'success');
          this.updateDebugUI();
        }
      } catch (err) {
        this.showNotification(`Error: ${err.message}`, 'error');
      }
    }

    async stepOut() {
      if (!this.debugSession) return;
      try {
        const result = await this.debugRequest(
          `/api/debug/step-out?session_id=${this.debugSession.session_id}`,
          { method: 'POST' }
        );
        if (result.success) {
          this.debugSession.current_line = result.current_line;
          this.showNotification(`Stepped out to line ${result.current_line}`, 'success');
          this.updateDebugUI();
        }
      } catch (err) {
        this.showNotification(`Error: ${err.message}`, 'error');
      }
    }

    async stopDebugSession() {
      if (!this.debugSession) return;
      try {
        const result = await this.debugRequest(
          `/api/debug/${this.debugSession.session_id}`,
          { method: 'DELETE' }
        );
        if (result.success) {
          this.debugSession = null;
          this.breakpoints = [];
          this.showNotification('Debug session stopped', 'success');
          this.updateDebugUI();
        }
      } catch (err) {
        this.showNotification(`Error: ${err.message}`, 'error');
      }
    }

    updateDebugUI() {
      const panel = $('#debug-panel');
      if (!panel) return;
      if (this.debugSession) {
        panel.classList.add('visible');
        const line = $('#current-line');
        if (line) line.textContent = `Line ${this.debugSession.current_line}`;
      } else {
        panel.classList.remove('visible');
      }
    }

    updateBreakpointsUI() {
      const list = $('#breakpoints-list');
      if (!list) return;
      list.innerHTML = this.breakpoints.map((bp, i) => `
        <div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:0.78rem;color:var(--text-secondary)">
          <span style="color:var(--accent-red)">●</span>
          <span>Line ${bp.line}${bp.condition ? ` (${bp.condition})` : ''}</span>
          <button class="remove-edit-btn" onclick="app.removeBreakpoint(${i})" style="margin-left:auto">Remove</button>
        </div>
      `).join('');
    }

    removeBreakpoint(index) {
      this.breakpoints.splice(index, 1);
      this.updateBreakpointsUI();
    }

    // ─── Sidebar ─────────────────────────────────────────────────────────────
    initSidebar() {
      $$('.sidebar-section-header').forEach(header => {
        header.addEventListener('click', () => {
          header.parentElement.classList.toggle('collapsed');
        });
      });

      $$('.sidebar-tab').forEach(tab => {
        tab.addEventListener('click', () => {
          $$('.sidebar-tab').forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          
          // Show/hide panels based on tab
          const tabName = tab.dataset.tab;
          const filesPanel = document.querySelector('.sidebar-section');
          const mcpPanel = document.getElementById('mcp-panel');
          const modelsPanel = document.getElementById('models-panel');
          
          if (filesPanel) filesPanel.style.display = tabName === 'files' ? 'block' : 'none';
          if (mcpPanel) mcpPanel.style.display = tabName === 'mcp' ? 'flex' : 'none';
          if (modelsPanel) modelsPanel.style.display = tabName === 'models' ? 'flex' : 'none';
        });
      });

      $$('.file-tree-item').forEach(item => {
        item.addEventListener('click', () => {
          $$('.file-tree-item').forEach(i => i.classList.remove('active'));
          item.classList.add('active');
        });
      });
    }

    // ─── Editor Tabs ─────────────────────────────────────────────────────────
    initEditorTabs() {
      $$('.editor-tab').forEach(tab => {
        tab.addEventListener('click', e => {
          if (e.target.closest('.tab-close')) {
            e.stopPropagation();
            tab.style.opacity = '0';
            tab.style.transform = 'scaleX(0)';
            setTimeout(() => tab.remove(), 200);
            return;
          }
          $$('.editor-tab').forEach(t => {
            t.classList.remove('active');
            t.setAttribute('aria-selected', 'false');
          });
          tab.classList.add('active');
          tab.setAttribute('aria-selected', 'true');
        });
      });
    }

    // ─── Textarea auto-resize ────────────────────────────────────────────────
    initTextarea() {
      const textarea = $('#query');
      const submit = $('#submit');
      if (!textarea) return;

      textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
        if (submit) submit.disabled = !textarea.value.trim();
      });

      textarea.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey && !(e.metaKey || e.ctrlKey)) {
          e.preventDefault();
          submit?.click();
        }
      });

      if (submit) {
        submit.addEventListener('click', () => {
          const value = textarea.value.trim();
          if (!value) return;
          this.addToHistory(value);
          this.setStatus('Processing...', 'active');
        });
      }
    }

    // ─── Status ──────────────────────────────────────────────────────────────
    initStatusDot() {
      this.setStatus('Ready', 'ready');
    }

    setStatus(text, state = 'ready') {
      const dot = $('#status-dot');
      const label = $('#status-text');
      if (label) label.textContent = text;
      if (dot) {
        dot.className = 'status-dot';
        if (state === 'error') dot.classList.add('error');
        else if (state === 'warning') dot.classList.add('warning');
      }
    }

    // ─── Panels ──────────────────────────────────────────────────────────────
    showMultiFileEdit() {
      $('#multi-file-edit-panel')?.classList.add('visible');
      $('#debug-panel')?.classList.remove('visible');
    }

    hideMultiFileEdit() {
      $('#multi-file-edit-panel')?.classList.remove('visible');
    }

    showDebugPanel() {
      $('#debug-panel')?.classList.add('visible');
      $('#multi-file-edit-panel')?.classList.remove('visible');
    }

    hideDebugPanel() {
      $('#debug-panel')?.classList.remove('visible');
    }

    // ─── Notifications ───────────────────────────────────────────────────────
    showNotification(message, type = 'info') {
      const container = $('#notification-container');
      if (!container) return;

      const icons = {
        success: 'fas fa-check',
        error: 'fas fa-times',
        warning: 'fas fa-exclamation',
        info: 'fas fa-info',
      };

      const el = document.createElement('div');
      el.className = `notification ${type}`;
      el.innerHTML = `
        <div class="notification-icon"><i class="${icons[type] || icons.info}"></i></div>
        <span>${message}</span>
        <button class="notification-close"><i class="fas fa-times"></i></button>
      `;

      container.appendChild(el);

      const remove = () => {
        el.classList.add('removing');
        setTimeout(() => el.remove(), 250);
      };

      $('.notification-close', el).addEventListener('click', remove);
      setTimeout(remove, 4000);
    }

    // ─── Auth ────────────────────────────────────────────────────────────────
    getAuthToken() {
      return localStorage.getItem('anvil-auth-token') || '';
    }
  }

  const app = new AnvilApp();
  window.app = app;
})();
