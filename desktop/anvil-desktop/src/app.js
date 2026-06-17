// Anvil Desktop App

class AnvilApp {
  constructor() {
    this.theme = localStorage.getItem('anvil-theme') || 'dark';
    this.chatHistory = [];
    this.currentModel = 'gpt-4o-mini';
    this.settings = {};
    this.init();
  }

  async init() {
    this.applyTheme();
    this.initEventListeners();
    await this.loadSettings();
    this.setStatus('Ready', 'ready');
    this.addChatMessage('assistant', 'Hello! I\'m Anvil, your AI coding assistant. Configure your API keys in Settings to get started.');
  }

  applyTheme() {
    document.documentElement.setAttribute('data-theme', this.theme);
    const icon = document.querySelector('#theme-toggle i');
    if (icon) icon.className = this.theme === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
  }

  toggleTheme() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('anvil-theme', this.theme);
    this.applyTheme();
  }

  async loadSettings() {
    try {
      const res = await fetch('http://localhost:8000/settings');
      this.settings = await res.json();
      this.currentModel = this.settings.default_model || 'gpt-4o-mini';
    } catch (e) {
      console.error('Failed to load settings:', e);
    }
  }

  async saveSettings(newSettings) {
    try {
      await fetch('http://localhost:8000/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      });
      this.settings = newSettings;
      this.showNotification('Settings saved', 'success');
    } catch (e) {
      this.showNotification('Failed to save settings', 'error');
    }
  }

  initEventListeners() {
    const submit = document.querySelector('#submit');
    const query = document.querySelector('#query');
    
    if (submit && query) {
      submit.addEventListener('click', () => this.handleChat());
      query.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.handleChat();
        }
      });
    }

    const settingsBtn = document.querySelector('#settings-btn');
    if (settingsBtn) {
      settingsBtn.addEventListener('click', () => this.showSettings());
    }

    const themeToggle = document.querySelector('#theme-toggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', () => this.toggleTheme());
    }
  }

  async handleChat() {
    const query = document.querySelector('#query');
    const response = document.querySelector('#response');
    
    if (!query || !query.value.trim()) return;

    const message = query.value.trim();
    query.value = '';
    
    this.addChatMessage('user', message);
    this.setStatus('Processing...', 'active');
    const loadingId = this.addChatMessage('assistant', 'Thinking...', true);

    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          model: this.currentModel,
        }),
      });

      const data = await res.json();
      
      this.removeChatMessage(loadingId);
      
      if (data.success) {
        this.addChatMessage('assistant', data.response);
        this.setStatus('Ready', 'ready');
      } else {
        this.addChatMessage('assistant', `Error: ${data.error}`, true);
        this.setStatus('Error', 'error');
      }
    } catch (e) {
      this.removeChatMessage(loadingId);
      this.addChatMessage('assistant', `Error: ${e.message}`, true);
      this.setStatus('Error', 'error');
    }
  }

  addChatMessage(role, content, isLoading = false) {
    const chat = document.querySelector('#chat-messages');
    if (!chat) return;

    const id = 'msg-' + Date.now();
    const msg = document.createElement('div');
    msg.id = id;
    msg.className = `chat-message ${role}`;
    msg.innerHTML = `
      <div class="message-avatar">${role === 'user' ? 'U' : 'A'}</div>
      <div class="message-content">
        <div class="message-role">${role === 'user' ? 'You' : 'Anvil'}</div>
        <div class="message-text">${isLoading ? '<em>' + content + '</em>' : this.escapeHtml(content)}</div>
      </div>
    `;
    chat.appendChild(msg);
    chat.scrollTop = chat.scrollHeight;
    return id;
  }

  removeChatMessage(id) {
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
    if (!modal) {
      this.createSettingsModal();
      modal = document.querySelector('#settings-modal');
    }
    
    const openaiKey = modal.querySelector('#openai-api-key');
    const anthropicKey = modal.querySelector('#anthropic-api-key');
    const geminiKey = modal.querySelector('#gemini-api-key');
    const deepseekKey = modal.querySelector('#deepseek-api-key');
    const groqKey = modal.querySelector('#groq-api-key');
    const mistralKey = modal.querySelector('#mistral-api-key');
    const defaultModel = modal.querySelector('#default-model');
    
    if (openaiKey) openaiKey.value = this.settings.openai_api_key || '';
    if (anthropicKey) anthropicKey.value = this.settings.anthropic_api_key || '';
    if (geminiKey) geminiKey.value = this.settings.gemini_api_key || '';
    if (deepseekKey) deepseekKey.value = this.settings.deepseek_api_key || '';
    if (groqKey) groqKey.value = this.settings.groq_api_key || '';
    if (mistralKey) mistralKey.value = this.settings.mistral_api_key || '';
    if (defaultModel) defaultModel.value = this.settings.default_model || 'gpt-4o-mini';
    
    modal.style.display = 'flex';
  }

  createSettingsModal() {
    const modal = document.createElement('div');
    modal.id = 'settings-modal';
    modal.className = 'modal';
    modal.innerHTML = `
      <div class="modal-content">
        <div class="modal-header">
          <h2>Settings</h2>
          <button class="modal-close" onclick="app.closeSettings()">&times;</button>
        </div>
        <div class="modal-body">
          <div class="settings-section">
            <h3>API Keys</h3>
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 16px;">
              Add your API keys to use cloud models. Keys are stored locally in ~/.anvil/settings.json
            </p>
            <div class="setting-item">
              <label>OpenAI API Key</label>
              <input type="password" id="openai-api-key" placeholder="sk-...">
            </div>
            <div class="setting-item">
              <label>Anthropic API Key</label>
              <input type="password" id="anthropic-api-key" placeholder="sk-ant-...">
            </div>
            <div class="setting-item">
              <label>Google Gemini API Key</label>
              <input type="password" id="gemini-api-key" placeholder="AI...">
            </div>
            <div class="setting-item">
              <label>DeepSeek API Key</label>
              <input type="password" id="deepseek-api-key" placeholder="sk-...">
            </div>
            <div class="setting-item">
              <label>Groq API Key</label>
              <input type="password" id="groq-api-key" placeholder="gsk-...">
            </div>
            <div class="setting-item">
              <label>Mistral API Key</label>
              <input type="password" id="mistral-api-key" placeholder="...">
            </div>
          </div>
          <div class="settings-section">
            <h3>Default Model</h3>
            <div class="setting-item">
              <label>Model</label>
              <select id="default-model">
                <option value="gpt-4o-mini">GPT-4o Mini (Fast & Cheap)</option>
                <option value="gpt-4o">GPT-4o (Powerful)</option>
                <option value="claude-3.5-sonnet">Claude 3.5 Sonnet</option>
                <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                <option value="deepseek-coder">DeepSeek Coder</option>
                <option value="groq/llama-3.1-70b">Groq Llama 3.1 70B (Fastest)</option>
                <option value="mistral-large">Mistral Large</option>
              </select>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary" onclick="app.closeSettings()">Cancel</button>
          <button class="btn btn-primary" onclick="app.saveSettingsFromModal()">Save</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }

  closeSettings() {
    const modal = document.querySelector('#settings-modal');
    if (modal) modal.style.display = 'none';
  }

  async saveSettingsFromModal() {
    const modal = document.querySelector('#settings-modal');
    if (!modal) return;

    const newSettings = {
      openai_api_key: modal.querySelector('#openai-api-key').value || null,
      anthropic_api_key: modal.querySelector('#anthropic-api-key').value || null,
      gemini_api_key: modal.querySelector('#gemini-api-key').value || null,
      deepseek_api_key: modal.querySelector('#deepseek-api-key').value || null,
      groq_api_key: modal.querySelector('#groq-api-key').value || null,
      mistral_api_key: modal.querySelector('#mistral-api-key').value || null,
      default_model: modal.querySelector('#default-model').value,
      workspace: this.settings.workspace || '.',
    };

    await this.saveSettings(newSettings);
    this.closeSettings();
  }

  setStatus(text, state = 'ready') {
    const dot = document.querySelector('#status-dot');
    const label = document.querySelector('#status-text');
    if (label) label.textContent = text;
    if (dot) {
      dot.className = 'status-dot';
      if (state === 'error') dot.classList.add('error');
      else if (state === 'warning') dot.classList.add('warning');
      else if (state === 'active') dot.classList.add('active');
    }
  }

  showNotification(message, type = 'info') {
    const container = document.querySelector('#notification-container');
    if (!container) return;

    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
      <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'times' : 'info'}"></i>
      <span>${message}</span>
    `;
    container.appendChild(notification);

    setTimeout(() => {
      notification.classList.add('fade-out');
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }
}

const app = new AnvilApp();
