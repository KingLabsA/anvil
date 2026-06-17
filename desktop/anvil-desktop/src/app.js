// Anvil Desktop — Calls Ollama directly from the browser

class AnvilDesktop {
  constructor() {
    this.theme = localStorage.getItem('anvil-theme') || 'dark';
    this.currentModel = '';
    this.ollamaModels = [];
    this.apiBase = localStorage.getItem('anvil-api-base') || 'http://localhost:11434';
    this.init();
  }

  async init() {
    this.applyTheme();
    this.initEvents();
    await this.loadModels();
    this.setStatus('Ready', 'ready');
  }

  applyTheme() {
    document.documentElement.setAttribute('data-theme', this.theme);
    const icon = document.querySelector('#theme-toggle i');
    if (icon) icon.className = this.theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
  }

  async loadModels() {
    const select = document.querySelector('#model-select');
    const list = document.querySelector('#models-list');

    try {
      const res = await fetch(`${this.apiBase}/api/tags`);
      const data = await res.json();
      this.ollamaModels = data.models || [];

      let html = '';
      this.ollamaModels.forEach(m => {
        const size = (m.size / 1e9).toFixed(1);
        html += `<option value="${m.name}">${m.name} (${size}GB)</option>`;
      });
      select.innerHTML = html || '<option>No models found</option>';

      if (this.ollamaModels.length > 0) {
        this.currentModel = this.ollamaModels[0].name;
        this.updateModelDisplay();
      }

      // Sidebar
      if (list) {
        let sideHtml = '';
        this.ollamaModels.forEach(m => {
          const size = (m.size / 1e9).toFixed(1);
          sideHtml += `<div class="nav-item" onclick="app.selectModel('${m.name}')">
            <span class="dot"></span>
            <span>${m.name}</span>
            <span class="badge">${size}GB</span>
          </div>`;
        });
        list.innerHTML = sideHtml;
      }
    } catch (e) {
      select.innerHTML = '<option>Ollama not running</option>';
    }

    // Load default model from settings
    const saved = localStorage.getItem('anvil-default-model');
    if (saved && this.ollamaModels.find(m => m.name === saved)) {
      this.currentModel = saved;
      select.value = saved;
      this.updateModelDisplay();
    }
  }

  selectModel(name) {
    this.currentModel = name;
    document.querySelector('#model-select').value = name;
    this.updateModelDisplay();
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.textContent.includes(name));
    });
  }

  updateModelDisplay() {
    const el = document.querySelector('#current-model');
    if (el) el.textContent = this.currentModel || 'No model';
  }

  initEvents() {
    const query = document.querySelector('#query');
    const submit = document.querySelector('#submit');

    if (query) {
      query.addEventListener('input', () => {
        query.style.height = 'auto';
        query.style.height = Math.min(query.scrollHeight, 200) + 'px';
        document.querySelector('#char-count').textContent = query.value.length;
      });
      query.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.handleChat();
        }
      });
    }

    if (submit) submit.addEventListener('click', () => this.handleChat());
    document.querySelector('#settings-btn')?.addEventListener('click', () => this.showSettings());
    document.querySelector('#theme-toggle')?.addEventListener('click', () => {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      localStorage.setItem('anvil-theme', this.theme);
      this.applyTheme();
    });
    document.querySelector('#model-select')?.addEventListener('change', (e) => {
      this.currentModel = e.target.value;
      this.updateModelDisplay();
    });
  }

  setQuickPrompt(text) {
    const query = document.querySelector('#query');
    if (query) {
      query.value = text;
      query.focus();
      query.dispatchEvent(new Event('input'));
    }
    document.querySelector('.welcome-screen')?.remove();
  }

  async handleChat() {
    const query = document.querySelector('#query');
    if (!query || !query.value.trim()) return;

    const message = query.value.trim();
    query.value = '';
    query.style.height = 'auto';
    document.querySelector('#char-count').textContent = '0';

    document.querySelector('.welcome-screen')?.remove();

    this.addMessage('user', message);
    this.setStatus('Thinking...', 'active');
    const thinkId = this.addMessage('assistant', '<div class="thinking"><span></span><span></span><span></span></div>', true);

    const model = this.currentModel || this.ollamaModels[0]?.name || 'shellwhisperer';

    try {
      const res = await fetch(`${this.apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: model,
          messages: [
            { role: 'system', content: 'You are Anvil, an expert AI coding assistant. Write clean, production-ready code.' },
            { role: 'user', content: message },
          ],
          stream: false,
        }),
      });

      const data = await res.json();
      this.removeMessage(thinkId);

      if (data.message && data.message.content) {
        this.addMessage('assistant', data.message.content);
        this.setStatus('Ready', 'ready');
      } else {
        this.addMessage('assistant', 'Error: No response from model');
        this.setStatus('Error', 'error');
      }
    } catch (e) {
      this.removeMessage(thinkId);
      this.addMessage('assistant', `Error: ${e.message}. Is Ollama running?`);
      this.setStatus('Error', 'error');
    }
  }

  addMessage(role, content, isLoading = false) {
    const chat = document.querySelector('#chat-messages');
    if (!chat) return;

    const id = 'msg-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = `chat-message ${role}`;

    const avatarClass = role === 'user' ? 'user-avatar' : 'ai-avatar';
    const avatarIcon = role === 'user' ? 'U' : '<i class="fas fa-hammer"></i>';
    const label = role === 'user' ? 'You' : 'Anvil';

    div.innerHTML = `
      <div class="msg-avatar ${avatarClass}">${avatarIcon}</div>
      <div class="msg-body">
        <div class="msg-label">${label}</div>
        <div class="msg-text">${isLoading ? content : this.escapeHtml(content)}</div>
      </div>
    `;

    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return id;
  }

  removeMessage(id) {
    const msg = document.querySelector('#' + id);
    if (msg) msg.remove();
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  showSettings() {
    const modal = document.querySelector('#settings-modal');
    if (modal) modal.style.display = 'flex';
  }

  closeSettings() {
    document.querySelector('#settings-modal').style.display = 'none';
  }

  saveSettings() {
    const base = document.querySelector('#api-base')?.value || 'http://localhost:11434';
    this.apiBase = base;
    localStorage.setItem('anvil-api-base', base);

    const defaultModel = document.querySelector('#default-model')?.value;
    if (defaultModel) {
      localStorage.setItem('anvil-default-model', defaultModel);
      this.currentModel = defaultModel;
      this.updateModelDisplay();
    }

    this.closeSettings();
    this.showNotification('Settings saved', 'success');
    this.loadModels();
  }

  setStatus(text, state) {
    const dot = document.querySelector('#status-dot');
    const label = document.querySelector('#status-text');
    if (label) label.textContent = text;
    if (dot) {
      dot.className = 'status-dot';
      if (state === 'error') dot.classList.add('error');
      else if (state === 'active') dot.classList.add('active');
    }
  }

  showNotification(message, type) {
    const container = document.querySelector('#notification-container');
    if (!container) return;
    const icons = { success: 'check-circle', error: 'exclamation-circle', info: 'info-circle' };
    const notif = document.createElement('div');
    notif.className = `notification ${type}`;
    notif.innerHTML = `<i class="fas fa-${icons[type] || 'info-circle'}"></i><span>${message}</span>`;
    container.appendChild(notif);
    setTimeout(() => {
      notif.classList.add('fade-out');
      setTimeout(() => notif.remove(), 300);
    }, 3000);
  }
}

const app = new AnvilDesktop();
