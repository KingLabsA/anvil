// Anvil Web App - Main Application Logic

class AnvilApp {
  constructor() {
    this.theme = localStorage.getItem('anvil-theme') || 'dark';
    this.applyTheme();
    this.initCommandPalette();
    this.initKeyboardShortcuts();
    this.initUndoRedo();
    this.initDragDrop();
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
}

// Initialize app
const app = new AnvilApp();
