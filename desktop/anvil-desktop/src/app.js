// Anvil Desktop - Standalone App
// Calls APIs directly from the browser - no backend server needed

const STORAGE_KEY = 'anvil-desktop';

class AnvilApp {
  constructor() {
    this.conversations = [];
    this.currentConvId = null;
    this.settings = this.loadSettings();
    this.abortController = null;
    this.init();
  }

  loadSettings() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY + '-settings');
      return raw ? JSON.parse(raw) : {
        keys: {},
        systemPrompt: 'You are Anvil, an expert AI coding assistant. Write clean, production-ready code. Explain your reasoning clearly.',
        maxTokens: 4096,
        temperature: 0.7,
        model: 'openai/gpt-4o-mini',
        theme: 'dark',
      };
    } catch { return { keys: {}, systemPrompt: '', maxTokens: 4096, temperature: 0.7, model: 'openai/gpt-4o-mini', theme: 'dark' }; }
  }

  saveSettings() {
    localStorage.setItem(STORAGE_KEY + '-settings', JSON.stringify(this.settings));
  }

  loadConversations() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY + '-conversations');
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  }

  saveConversations() {
    localStorage.setItem(STORAGE_KEY + '-conversations', JSON.stringify(this.conversations));
  }

  init() {
    this.conversations = this.loadConversations();
    this.applyTheme();
    this.bindEvents();
    this.renderConversations();
    this.showWelcome();
    this.setStatus('Ready', 'success');
  }

  applyTheme() {
    document.documentElement.setAttribute('data-theme', this.settings.theme);
    const btn = document.getElementById('btn-theme');
    if (btn) btn.innerHTML = this.settings.theme === 'dark' ? '&#9790;' : '&#9728;';
  }

  bindEvents() {
    document.getElementById('btn-settings').addEventListener('click', () => this.openSettings());
    document.getElementById('btn-close-settings').addEventListener('click', () => this.closeSettings());
    document.getElementById('btn-save-settings').addEventListener('click', () => this.saveSettingsModal());
    document.getElementById('btn-theme').addEventListener('click', () => this.toggleTheme());
    document.getElementById('btn-new-chat').addEventListener('click', () => this.newConversation());
    document.getElementById('btn-send').addEventListener('click', () => this.send());

    const input = document.getElementById('input');
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.send();
      }
    });
    input.addEventListener('input', () => this.autoResize(input));

    document.getElementById('settings-modal').addEventListener('click', (e) => {
      if (e.target.id === 'settings-modal') this.closeSettings();
    });

    document.getElementById('model-select').value = this.settings.model;
    document.getElementById('model-select').addEventListener('change', (e) => {
      this.settings.model = e.target.value;
      this.saveSettings();
    });
  }

  autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 150) + 'px';
  }

  newConversation() {
    const conv = {
      id: Date.now().toString(),
      title: 'New Chat',
      messages: [],
      createdAt: new Date().toISOString(),
    };
    this.conversations.unshift(conv);
    this.currentConvId = conv.id;
    this.saveConversations();
    this.renderConversations();
    this.renderMessages();
    document.getElementById('input').focus();
  }

  renderConversations() {
    const list = document.getElementById('conversations');
    list.innerHTML = this.conversations.map(c => `
      <div class="conv-item ${c.id === this.currentConvId ? 'active' : ''}"
           data-id="${c.id}">
        ${this.escapeHtml(c.title)}
      </div>
    `).join('');

    list.querySelectorAll('.conv-item').forEach(el => {
      el.addEventListener('click', () => {
        this.currentConvId = el.dataset.id;
        this.renderConversations();
        this.renderMessages();
      });
    });
  }

  showWelcome() {
    const messages = document.getElementById('messages');
    messages.innerHTML = `
      <div class="welcome">
        <div class="welcome-icon">&#9874;</div>
        <h2>What can I help you build?</h2>
        <p>An expert coding assistant. Ask me to write code, debug issues, explain concepts, or architect systems.</p>
        <div class="shortcuts">
          <div class="shortcut" onclick="app.insertPrompt('Write a Python web scraper for')"><kbd>&#128270;</kbd>Write a scraper</div>
          <div class="shortcut" onclick="app.insertPrompt('Fix this bug:')"><kbd>&#128027;</kbd>Fix a bug</div>
          <div class="shortcut" onclick="app.insertPrompt('Explain how')"><kbd>&#128218;</kbd>Explain code</div>
          <div class="shortcut" onclick="app.insertPrompt('Build a REST API with')"><kbd>&#128640;</kbd>Build an API</div>
        </div>
      </div>
    `;
  }

  insertPrompt(text) {
    const input = document.getElementById('input');
    input.value = text + ' ';
    input.focus();
  }

  renderMessages() {
    const conv = this.conversations.find(c => c.id === this.currentConvId);
    if (!conv || conv.messages.length === 0) {
      this.showWelcome();
      return;
    }

    const messages = document.getElementById('messages');
    messages.innerHTML = conv.messages.map(m => `
      <div class="message ${m.role}">
        <div class="message-header">
          <span class="message-role ${m.role}">${m.role === 'user' ? 'You' : 'Anvil'}</span>
        </div>
        <div class="message-content">${this.formatContent(m.content)}</div>
      </div>
    `).join('');

    messages.scrollTop = messages.scrollHeight;
  }

  formatContent(text) {
    if (!text) return '';
    let html = this.escapeHtml(text);
    // Code blocks
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>');
    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    return html;
  }

  escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  setStatus(text, cls) {
    const el = document.getElementById('status');
    el.textContent = text;
    el.className = 'status ' + (cls || '');
  }

  async send() {
    const input = document.getElementById('input');
    const message = input.value.trim();
    if (!message) return;

    // Ensure we have a conversation
    if (!this.currentConvId) {
      this.newConversation();
    }

    const conv = this.conversations.find(c => c.id === this.currentConvId);
    if (!conv) return;

    // Add user message
    conv.messages.push({ role: 'user', content: message });
    if (conv.messages.length === 1) {
      conv.title = message.substring(0, 60);
      this.renderConversations();
    }
    this.saveConversations();
    this.renderMessages();

    input.value = '';
    input.style.height = 'auto';

    // Show thinking
    const thinkingId = this.addThinking();
    this.setStatus('Thinking...', 'active');
    document.getElementById('btn-send').disabled = true;

    try {
      const response = await this.callAPI(conv);
      this.removeThinking(thinkingId);
      conv.messages.push({ role: 'assistant', content: response });
      this.saveConversations();
      this.renderMessages();
      this.setStatus('Ready', 'success');
    } catch (err) {
      this.removeThinking(thinkingId);
      const errMsg = err.message || 'Failed to get response';
      conv.messages.push({ role: 'assistant', content: `Error: ${errMsg}` });
      this.saveConversations();
      this.renderMessages();
      this.setStatus('Error: ' + errMsg, 'error');
    }

    document.getElementById('btn-send').disabled = false;
  }

  addThinking() {
    const messages = document.getElementById('messages');
    const id = 'thinking-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'message assistant';
    div.innerHTML = `
      <div class="message-header">
        <span class="message-role assistant">Anvil</span>
      </div>
      <div class="thinking">
        <div class="thinking-dot"></div>
        <div class="thinking-dot"></div>
        <div class="thinking-dot"></div>
      </div>
    `;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return id;
  }

  removeThinking(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  async callAPI(conv) {
    const model = this.settings.model;
    const [provider, modelId] = model.split('/');

    const messages = [
      { role: 'system', content: this.settings.systemPrompt || 'You are Anvil, an expert AI coding assistant.' },
      ...conv.messages.map(m => ({ role: m.role, content: m.content })),
    ];

    this.abortController = new AbortController();

    if (provider === 'openai' || provider === 'deepseek' || provider === 'groq' || provider === 'mistral') {
      return this.callOpenAICompatible(provider, modelId, messages);
    } else if (provider === 'anthropic') {
      return this.callAnthropic(modelId, messages);
    } else if (provider === 'google') {
      return this.callGemini(modelId, messages);
    }

    throw new Error(`Unsupported provider: ${provider}`);
  }

  getAPIKey(provider) {
    const keyMap = {
      openai: 'key-openai',
      anthropic: 'key-anthropic',
      google: 'key-gemini',
      deepseek: 'key-deepseek',
      groq: 'key-groq',
      mistral: 'key-mistral',
    };
    const input = document.getElementById(keyMap[provider]);
    return input ? input.value.trim() : '';
  }

  getBaseURL(provider) {
    const urls = {
      openai: 'https://api.openai.com/v1',
      deepseek: 'https://api.deepseek.com/v1',
      groq: 'https://api.groq.com/openai/v1',
      mistral: 'https://api.mistral.ai/v1',
    };
    return urls[provider] || 'https://api.openai.com/v1';
  }

  async callOpenAICompatible(provider, modelId, messages) {
    const apiKey = this.getAPIKey(provider);
    if (!apiKey) throw new Error(`No API key for ${provider}. Open Settings to add one.`);

    const res = await fetch(`${this.getBaseURL(provider)}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: modelId,
        messages,
        max_tokens: this.settings.maxTokens,
        temperature: this.settings.temperature,
      }),
      signal: this.abortController.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || `API error ${res.status}`);
    }

    const data = await res.json();
    return data.choices?.[0]?.message?.content || 'No response';
  }

  async callAnthropic(modelId, messages) {
    const apiKey = this.getAPIKey('anthropic');
    if (!apiKey) throw new Error('No API key for Anthropic. Open Settings to add one.');

    const systemMsg = messages.find(m => m.role === 'system');
    const chatMsgs = messages.filter(m => m.role !== 'system');

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: modelId,
        max_tokens: this.settings.maxTokens,
        system: systemMsg?.content || '',
        messages: chatMsgs,
      }),
      signal: this.abortController.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || `API error ${res.status}`);
    }

    const data = await res.json();
    return data.content?.[0]?.text || 'No response';
  }

  async callGemini(modelId, messages) {
    const apiKey = this.getAPIKey('google');
    if (!apiKey) throw new Error('No API key for Google Gemini. Open Settings to add one.');

    const contents = messages
      .filter(m => m.role !== 'system')
      .map(m => ({
        role: m.role === 'assistant' ? 'model' : 'user',
        parts: [{ text: m.content }],
      }));

    const systemInstruction = messages.find(m => m.role === 'system');

    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${modelId}:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents,
          ...(systemInstruction ? { systemInstruction: { parts: [{ text: systemInstruction.content }] } } : {}),
          generationConfig: {
            maxOutputTokens: this.settings.maxTokens,
            temperature: this.settings.temperature,
          },
        }),
        signal: this.abortController.signal,
      }
    );

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error?.message || `API error ${res.status}`);
    }

    const data = await res.json();
    return data.candidates?.[0]?.content?.parts?.[0]?.text || 'No response';
  }

  openSettings() {
    const modal = document.getElementById('settings-modal');
    modal.classList.remove('hidden');

    document.getElementById('key-openai').value = this.settings.keys?.openai || '';
    document.getElementById('key-anthropic').value = this.settings.keys?.anthropic || '';
    document.getElementById('key-gemini').value = this.settings.keys?.google || '';
    document.getElementById('key-deepseek').value = this.settings.keys?.deepseek || '';
    document.getElementById('key-groq').value = this.settings.keys?.groq || '';
    document.getElementById('key-mistral').value = this.settings.keys?.mistral || '';
    document.getElementById('system-prompt').value = this.settings.systemPrompt || '';
    document.getElementById('max-tokens').value = this.settings.maxTokens || 4096;
    document.getElementById('temperature').value = this.settings.temperature || 0.7;
  }

  closeSettings() {
    document.getElementById('settings-modal').classList.add('hidden');
  }

  saveSettingsModal() {
    this.settings.keys = {
      openai: document.getElementById('key-openai').value.trim(),
      anthropic: document.getElementById('key-anthropic').value.trim(),
      google: document.getElementById('key-gemini').value.trim(),
      deepseek: document.getElementById('key-deepseek').value.trim(),
      groq: document.getElementById('key-groq').value.trim(),
      mistral: document.getElementById('key-mistral').value.trim(),
    };
    this.settings.systemPrompt = document.getElementById('system-prompt').value;
    this.settings.maxTokens = parseInt(document.getElementById('max-tokens').value) || 4096;
    this.settings.temperature = parseFloat(document.getElementById('temperature').value) || 0.7;
    this.saveSettings();
    this.closeSettings();
    this.setStatus('Settings saved', 'success');
  }

  toggleTheme() {
    this.settings.theme = this.settings.theme === 'dark' ? 'light' : 'dark';
    this.saveSettings();
    this.applyTheme();
  }
}

const app = new AnvilApp();
