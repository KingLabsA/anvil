// Anvil Web App - Main Application Logic

class AnvilApp {
  constructor() {
    this.theme = localStorage.getItem('anvil-theme') || 'dark';
    this.applyTheme();
    this.initCommandPalette();
    this.initKeyboardShortcuts();
    this.initUndoRedo();
    this.initDragDrop();
    this.initMultiFileEdit();
    this.initDebugging();
  }

  // Theme Management
  applyTheme() {
    document.documentElement.setAttribute('data-theme', this.theme);
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
      themeToggle.textContent = this.theme === 'dark' ? '☀️' : '🌙';
    }
  }

  toggleTheme() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('anvil-theme', this.theme);
    this.applyTheme();
  }

  // Command Palette
  initCommandPalette() {
    const palette = document.getElementById('command-palette');
    const input = document.getElementById('command-input');
    const results = document.getElementById('command-results');
    
    if (!palette || !input || !results) return;

    // Toggle palette with Cmd/Ctrl+K
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        this.toggleCommandPalette();
      }
      if (e.key === 'Escape') {
        this.hideCommandPalette();
      }
    });

    // Filter commands
    input.addEventListener('input', (e) => {
      this.filterCommands(e.target.value);
    });

    // Handle command selection
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const selected = results.querySelector('.command-item.selected');
        if (selected) {
          this.executeCommand(selected.dataset.command);
        }
      }
    });
  }

  toggleCommandPalette() {
    const palette = document.getElementById('command-palette');
    if (palette.style.display === 'none') {
      this.showCommandPalette();
    } else {
      this.hideCommandPalette();
    }
  }

  showCommandPalette() {
    const palette = document.getElementById('command-palette');
    const input = document.getElementById('command-input');
    palette.style.display = 'block';
    input.focus();
    this.filterCommands('');
  }

  hideCommandPalette() {
    const palette = document.getElementById('command-palette');
    palette.style.display = 'none';
  }

  filterCommands(query) {
    const results = document.getElementById('command-results');
    const commands = this.getCommands();
    const filtered = commands.filter(cmd => 
      cmd.name.toLowerCase().includes(query.toLowerCase()) ||
      cmd.description.toLowerCase().includes(query.toLowerCase())
    );

    results.innerHTML = filtered.map((cmd, i) => `
      <div class="command-item ${i === 0 ? 'selected' : ''}" 
           data-command="${cmd.action}"
           onclick="app.executeCommand('${cmd.action}')">
        <div class="command-name">${cmd.name}</div>
        <div class="command-description">${cmd.description}</div>
      </div>
    `).join('');
  }

  getCommands() {
    return [
      { name: 'Toggle Theme', description: 'Switch between dark and light mode', action: 'toggleTheme' },
      { name: 'New Task', description: 'Create a new task', action: 'newTask' },
      { name: 'Run Task', description: 'Run the current task', action: 'runTask' },
      { name: 'Analyze Code', description: 'Analyze code for issues', action: 'analyzeCode' },
      { name: 'Explain Code', description: 'Explain selected code', action: 'explainCode' },
      { name: 'Optimize Code', description: 'Optimize selected code', action: 'optimizeCode' },
      { name: 'Review Code', description: 'Review selected code', action: 'reviewCode' },
      { name: 'Fix Issues', description: 'Fix issues in code', action: 'fixIssues' },
      { name: 'Clear Output', description: 'Clear the output panel', action: 'clearOutput' },
      { name: 'Settings', description: 'Open settings', action: 'openSettings' },
    ];
  }

  executeCommand(action) {
    this.hideCommandPalette();
    switch (action) {
      case 'toggleTheme':
        this.toggleTheme();
        break;
      case 'newTask':
        document.getElementById('query').value = '';
        document.getElementById('query').focus();
        break;
      case 'runTask':
        document.getElementById('submit').click();
        break;
      case 'analyzeCode':
        this.quickAction('analyze');
        break;
      case 'explainCode':
        this.quickAction('explain');
        break;
      case 'optimizeCode':
        this.quickAction('optimize');
        break;
      case 'reviewCode':
        this.quickAction('review');
        break;
      case 'fixIssues':
        this.quickAction('fix');
        break;
      case 'clearOutput':
        document.getElementById('response').style.display = 'none';
        break;
      case 'openSettings':
        // Open settings modal
        break;
    }
  }

  // Keyboard Shortcuts
  initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Cmd/Ctrl+Enter to run task
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        document.getElementById('submit').click();
      }
      
      // Cmd/Ctrl+/ to focus search
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault();
        document.getElementById('query').focus();
      }
      
      // Cmd/Ctrl+Shift+C to copy output
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'C') {
        e.preventDefault();
        this.copyOutput();
      }
    });
  }

  // Undo/Redo System
  initUndoRedo() {
    this.history = [];
    this.historyIndex = -1;
    
    // Listen for input changes
    const query = document.getElementById('query');
    if (query) {
      query.addEventListener('input', () => {
        this.addToHistory(query.value);
      });
    }
    
    // Undo/Redo shortcuts
    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        this.undo();
      }
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === 'z') {
        e.preventDefault();
        this.redo();
      }
    });
  }

  addToHistory(value) {
    // Remove future history if we're not at the end
    if (this.historyIndex < this.history.length - 1) {
      this.history = this.history.slice(0, this.historyIndex + 1);
    }
    
    this.history.push(value);
    this.historyIndex = this.history.length - 1;
    
    // Limit history size
    if (this.history.length > 100) {
      this.history.shift();
      this.historyIndex--;
    }
  }

  undo() {
    if (this.historyIndex > 0) {
      this.historyIndex--;
      const query = document.getElementById('query');
      if (query) {
        query.value = this.history[this.historyIndex];
      }
    }
  }

  redo() {
    if (this.historyIndex < this.history.length - 1) {
      this.historyIndex++;
      const query = document.getElementById('query');
      if (query) {
        query.value = this.history[this.historyIndex];
      }
    }
  }

  // Drag and Drop
  initDragDrop() {
    const dropZone = document.getElementById('drop-zone');
    if (!dropZone) return;

    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
      dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        this.handleFileDrop(files[0]);
      }
    });
  }

  async handleFileDrop(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const query = document.getElementById('query');
      if (query) {
        query.value = `Analyze this ${file.name}:\n\n${e.target.result}`;
      }
    };
    reader.readAsText(file);
  }

  // Quick Actions
  async quickAction(action) {
    const selection = window.getSelection().toString();
    const prompts = {
      analyze: 'Analyze this code for issues:',
      explain: 'Explain this code in simple terms:',
      optimize: 'Optimize this code for performance and readability:',
      review: 'Review this code for bugs, security issues, and best practices:',
      fix: 'Fix any issues in this code:'
    };

    const prompt = prompts[action];
    const query = document.getElementById('query');
    
    if (selection) {
      query.value = `${prompt}\n\n\`\`\`\n${selection}\n\`\`\``;
    } else {
      query.value = prompt;
    }
    
    document.getElementById('submit').click();
  }

  // Copy Output
  copyOutput() {
    const response = document.getElementById('response-content');
    if (response) {
      navigator.clipboard.writeText(response.textContent);
      // Show feedback
      const btn = document.getElementById('copy');
      if (btn) {
        btn.textContent = '✓';
        setTimeout(() => {
          btn.textContent = '📋';
        }, 2000);
      }
    }
  }

  // Multi-File Editing
  initMultiFileEdit() {
    this.multiFileEdits = [];
    this.initMultiFileEditUI();
  }

  initMultiFileEditUI() {
    const addEditBtn = document.getElementById('add-multi-edit');
    if (addEditBtn) {
      addEditBtn.addEventListener('click', () => this.addMultiFileEdit());
    }
  }

  addMultiFileEdit() {
    const container = document.getElementById('multi-edit-container');
    if (!container) return;

    const editItem = document.createElement('div');
    editItem.className = 'multi-edit-item';
    editItem.innerHTML = `
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

    container.appendChild(editItem);

    const removeBtn = editItem.querySelector('.remove-edit-btn');
    removeBtn.addEventListener('click', () => {
      editItem.remove();
      this.multiFileEdits = this.multiFileEdits.filter(item => item !== editItem);
    });

    this.multiFileEdits.push(editItem);
  }

  async submitMultiFileEdit() {
    const edits = [];
    const items = document.querySelectorAll('.multi-edit-item');
    
    items.forEach(item => {
      const action = item.querySelector('.edit-action').value;
      const path = item.querySelector('.edit-path').value;
      const content = item.querySelector('.edit-content').value;
      
      if (path) {
        const edit = { action, path };
        if (action !== 'delete') {
          edit.content = content;
        }
        edits.push(edit);
      }
    });

    if (edits.length === 0) {
      this.showNotification('No files to edit', 'error');
      return;
    }

    try {
      const response = await fetch('/api/multi-edit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`
        },
        body: JSON.stringify({
          edits,
          description: 'Multi-file edit',
          auto_verify: true
        })
      });

      const result = await response.json();
      
      if (result.success) {
        this.showNotification(`Successfully edited ${result.files_changed.length} file(s)`, 'success');
        this.multiFileEdits = [];
        document.getElementById('multi-edit-container').innerHTML = '';
      } else {
        this.showNotification(`Error: ${result.errors.join(', ')}`, 'error');
      }
    } catch (error) {
      this.showNotification(`Error: ${error.message}`, 'error');
    }
  }

  // Debugging
  initDebugging() {
    this.debugSession = null;
    this.breakpoints = [];
    this.initDebuggingUI();
  }

  initDebuggingUI() {
    const startDebugBtn = document.getElementById('start-debug');
    const addBreakpointBtn = document.getElementById('add-breakpoint');
    const continueBtn = document.getElementById('continue-debug');
    const stepOverBtn = document.getElementById('step-over');
    const stepIntoBtn = document.getElementById('step-into');
    const stepOutBtn = document.getElementById('step-out');
    const stopDebugBtn = document.getElementById('stop-debug');

    if (startDebugBtn) {
      startDebugBtn.addEventListener('click', () => this.startDebugSession());
    }
    if (addBreakpointBtn) {
      addBreakpointBtn.addEventListener('click', () => this.addBreakpoint());
    }
    if (continueBtn) {
      continueBtn.addEventListener('click', () => this.continueDebug());
    }
    if (stepOverBtn) {
      stepOverBtn.addEventListener('click', () => this.stepOver());
    }
    if (stepIntoBtn) {
      stepIntoBtn.addEventListener('click', () => this.stepInto());
    }
    if (stepOutBtn) {
      stepOutBtn.addEventListener('click', () => this.stepOut());
    }
    if (stopDebugBtn) {
      stopDebugBtn.addEventListener('click', () => this.stopDebugSession());
    }
  }

  async startDebugSession() {
    const fileInput = document.getElementById('debug-file');
    if (!fileInput || !fileInput.value) {
      this.showNotification('Please select a file to debug', 'error');
      return;
    }

    try {
      const response = await fetch(`/api/debug/start?file=${encodeURIComponent(fileInput.value)}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.getAuthToken()}`
        }
      });

      const session = await response.json();
      this.debugSession = session;
      this.showNotification('Debug session started', 'success');
      this.updateDebugUI();
    } catch (error) {
      this.showNotification(`Error: ${error.message}`, 'error');
    }
  }

  async addBreakpoint() {
    if (!this.debugSession) {
      this.showNotification('No active debug session', 'error');
      return;
    }

    const lineInput = document.getElementById('breakpoint-line');
    const conditionInput = document.getElementById('breakpoint-condition');
    
    if (!lineInput || !lineInput.value) {
      this.showNotification('Please enter a line number', 'error');
      return;
    }

    try {
      const response = await fetch('/api/debug/breakpoint', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`
        },
        body: JSON.stringify({
          session_id: this.debugSession.session_id,
          breakpoint: {
            file: this.debugSession.file,
            line: parseInt(lineInput.value),
            condition: conditionInput ? conditionInput.value : null,
            enabled: true
          }
        })
      });

      const result = await response.json();
      if (result.success) {
        this.breakpoints.push(result.breakpoint);
        this.showNotification('Breakpoint added', 'success');
        this.updateBreakpointsUI();
      }
    } catch (error) {
      this.showNotification(`Error: ${error.message}`, 'error');
    }
  }

  async continueDebug() {
    if (!this.debugSession) return;

    try {
      const response = await fetch(`/api/debug/continue?session_id=${this.debugSession.session_id}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.getAuthToken()}`
        }
      });

      const result = await response.json();
      if (result.success) {
        this.debugSession.current_line = result.current_line;
        this.showNotification(`Execution continued to line ${result.current_line}`, 'success');
        this.updateDebugUI();
      }
    } catch (error) {
      this.showNotification(`Error: ${error.message}`, 'error');
    }
  }

  async stepOver() {
    if (!this.debugSession) return;

    try {
      const response = await fetch(`/api/debug/step-over?session_id=${this.debugSession.session_id}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.getAuthToken()}`
        }
      });

      const result = await response.json();
      if (result.success) {
        this.debugSession.current_line = result.current_line;
        this.showNotification(`Stepped over to line ${result.current_line}`, 'success');
        this.updateDebugUI();
      }
    } catch (error) {
      this.showNotification(`Error: ${error.message}`, 'error');
    }
  }

  async stepInto() {
    if (!this.debugSession) return;

    try {
      const response = await fetch(`/api/debug/step-into?session_id=${this.debugSession.session_id}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.getAuthToken()}`
        }
      });

      const result = await response.json();
      if (result.success) {
        this.debugSession.current_line = result.current_line;
        this.showNotification(`Stepped into line ${result.current_line}`, 'success');
        this.updateDebugUI();
      }
    } catch (error) {
      this.showNotification(`Error: ${error.message}`, 'error');
    }
  }

  async stepOut() {
    if (!this.debugSession) return;

    try {
      const response = await fetch(`/api/debug/step-out?session_id=${this.debugSession.session_id}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.getAuthToken()}`
        }
      });

      const result = await response.json();
      if (result.success) {
        this.debugSession.current_line = result.current_line;
        this.showNotification(`Stepped out to line ${result.current_line}`, 'success');
        this.updateDebugUI();
      }
    } catch (error) {
      this.showNotification(`Error: ${error.message}`, 'error');
    }
  }

  async stopDebugSession() {
    if (!this.debugSession) return;

    try {
      const response = await fetch(`/api/debug/${this.debugSession.session_id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this.getAuthToken()}`
        }
      });

      const result = await response.json();
      if (result.success) {
        this.debugSession = null;
        this.breakpoints = [];
        this.showNotification('Debug session stopped', 'success');
        this.updateDebugUI();
      }
    } catch (error) {
      this.showNotification(`Error: ${error.message}`, 'error');
    }
  }

  updateDebugUI() {
    const debugPanel = document.getElementById('debug-panel');
    if (!debugPanel) return;

    if (this.debugSession) {
      debugPanel.style.display = 'block';
      const currentLineEl = document.getElementById('current-line');
      if (currentLineEl) {
        currentLineEl.textContent = this.debugSession.current_line;
      }
    } else {
      debugPanel.style.display = 'none';
    }
  }

  updateBreakpointsUI() {
    const breakpointsList = document.getElementById('breakpoints-list');
    if (!breakpointsList) return;

    breakpointsList.innerHTML = this.breakpoints.map((bp, index) => `
      <div class="breakpoint-item">
        <span>Line ${bp.line}${bp.condition ? ` (${bp.condition})` : ''}</span>
        <button onclick="app.removeBreakpoint(${index})">Remove</button>
      </div>
    `).join('');
  }

  removeBreakpoint(index) {
    this.breakpoints.splice(index, 1);
    this.updateBreakpointsUI();
  }

  getAuthToken() {
    return localStorage.getItem('anvil-auth-token') || '';
  }

  showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
      notification.remove();
    }, 3000);
  }

  // Panel management
  showMultiFileEdit() {
    document.getElementById('multi-file-edit-panel').style.display = 'block';
    document.getElementById('debug-panel').style.display = 'none';
  }

  hideMultiFileEdit() {
    document.getElementById('multi-file-edit-panel').style.display = 'none';
  }

  showDebugPanel() {
    document.getElementById('debug-panel').style.display = 'block';
    document.getElementById('multi-file-edit-panel').style.display = 'none';
  }

  hideDebugPanel() {
    document.getElementById('debug-panel').style.display = 'none';
  }
}

// Initialize app
const app = new AnvilApp();

// Global functions for HTML onclick handlers
function showMultiFileEdit() {
  app.showMultiFileEdit();
}

function hideMultiFileEdit() {
  app.hideMultiFileEdit();
}

function showDebugPanel() {
  app.showDebugPanel();
}

function hideDebugPanel() {
  app.hideDebugPanel();
}
