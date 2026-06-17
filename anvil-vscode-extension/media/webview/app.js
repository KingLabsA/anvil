(function () {
  const vscode = acquireVsCodeApi();

  const chatContainer = document.getElementById('chat-container');
  const chatEmpty = document.getElementById('chat-empty');
  const inputArea = document.getElementById('input-area');
  const sendBtn = document.getElementById('send-btn');
  const statusIndicator = document.getElementById('status-indicator');
  const footerModel = document.getElementById('footer-model');
  const footerTokens = document.getElementById('footer-tokens');
  const toolbarBtns = document.querySelectorAll('.toolbar-btn');

  let currentTheme = 'dark';
  let totalTokens = 0;

  function init() {
    vscode.postMessage({ type: 'ready' });
    bindEvents();
  }

  function bindEvents() {
    sendBtn.addEventListener('click', handleSend);

    inputArea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    inputArea.addEventListener('input', () => {
      inputArea.style.height = 'auto';
      inputArea.style.height = Math.min(inputArea.scrollHeight, 120) + 'px';
    });

    toolbarBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        const action = btn.getAttribute('data-action');
        if (action) {
          vscode.postMessage({
            type: 'request',
            data: { action, code: inputArea.value },
          });
          inputArea.value = '';
          inputArea.style.height = 'auto';
        }
      });
    });
  }

  function handleSend() {
    const text = inputArea.value.trim();
    if (!text) return;

    addMessage('user', text);
    vscode.postMessage({
      type: 'request',
      data: { action: 'ask', code: text },
    });

    inputArea.value = '';
    inputArea.style.height = 'auto';
  }

  function addMessage(role, content) {
    if (chatEmpty) {
      chatEmpty.style.display = 'none';
    }

    const msg = document.createElement('div');
    msg.className = `chat-message chat-message-${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? 'U' : '\u2692';

    const body = document.createElement('div');
    body.className = 'message-body';

    const text = document.createElement('div');
    text.className = 'message-text';
    text.textContent = content;

    body.appendChild(text);
    msg.appendChild(avatar);
    msg.appendChild(body);
    chatContainer.appendChild(msg);

    chatContainer.scrollTop = chatContainer.scrollHeight;
    return text;
  }

  function addLoadingMessage() {
    if (chatEmpty) {
      chatEmpty.style.display = 'none';
    }

    const msg = document.createElement('div');
    msg.className = 'chat-message chat-message-assistant';
    msg.id = 'loading-message';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = '\u2692';

    const body = document.createElement('div');
    body.className = 'message-body';

    const dots = document.createElement('div');
    dots.className = 'loading-dots';
    dots.innerHTML = '<span></span><span></span><span></span>';

    body.appendChild(dots);
    msg.appendChild(avatar);
    msg.appendChild(body);
    chatContainer.appendChild(msg);

    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  function removeLoadingMessage() {
    const el = document.getElementById('loading-message');
    if (el) el.remove();
  }

  function updateStatus(connected) {
    const dot = statusIndicator.querySelector('.status-dot');
    const text = statusIndicator.querySelector('.status-text');
    if (connected) {
      dot.classList.add('connected');
      dot.classList.remove('disconnected');
      text.textContent = 'Connected';
    } else {
      dot.classList.remove('connected');
      dot.classList.add('disconnected');
      text.textContent = 'Disconnected';
    }
  }

  function updateTheme(theme) {
    currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    document.body.className = `anvil-${theme}`;
  }

  window.addEventListener('message', (event) => {
    const message = event.data;

    switch (message.type) {
      case 'response': {
        removeLoadingMessage();

        if (message.data?.status) {
          updateStatus(message.data.connected);
          return;
        }

        if (message.data?.config) {
          const cfg = message.data.config;
          footerModel.textContent = `Model: ${cfg.model}`;
          return;
        }

        if (message.data?.theme) {
          updateTheme(message.data.theme);
          return;
        }

        if (message.data?.stream) {
          const existing = document.querySelector('.chat-message-assistant:last-child .message-text');
          if (existing && existing.dataset.streaming === 'true') {
            existing.textContent = message.data.partial || '';
            chatContainer.scrollTop = chatContainer.scrollHeight;
          } else {
            const textEl = addMessage('assistant', message.data.partial || message.data.stream);
            textEl.dataset.streaming = 'true';
          }
          return;
        }

        if (message.data?.result) {
          const result = message.data.result;

          const lastStreaming = document.querySelector('.message-text[data-streaming="true"]');
          if (lastStreaming) {
            lastStreaming.dataset.streaming = 'false';
            if (result.result) {
              lastStreaming.textContent = result.result;
            }
          } else if (result.result) {
            addMessage('assistant', result.result);
          }

          if (result.tokens) {
            totalTokens += result.tokens.total || 0;
            footerTokens.textContent = `Tokens: ${totalTokens.toLocaleString()}`;
          }

          if (result.verification) {
            addVerificationBadge(result.verification);
          }
        }

        if (message.data?.loading === false) {
          const sendBtnEl = sendBtn;
          sendBtnEl.disabled = false;
          sendBtnEl.textContent = '\u27A8';
        }
        break;
      }

      case 'error': {
        removeLoadingMessage();
        const errorMsg = message.data?.message || 'Unknown error';
        addMessage('assistant', `Error: ${errorMsg}`);
        const lastMsg = chatContainer.querySelector('.chat-message-assistant:last-child .message-text');
        if (lastMsg) lastMsg.classList.add('message-error');
        break;
      }

      case 'request': {
        if (message.data?.loading) {
          addLoadingMessage();
          sendBtn.disabled = true;
          sendBtn.textContent = '\u23F3';
        }
        break;
      }
    }
  });

  function addVerificationBadge(verification) {
    const badge = document.createElement('div');
    badge.className = `verification-badge ${verification.passed ? 'passed' : 'failed'}`;

    const icon = document.createElement('span');
    icon.className = 'badge-icon';
    icon.textContent = verification.passed ? '\u2705' : '\u274C';

    const label = document.createElement('span');
    label.className = 'badge-label';
    label.textContent = `Verification: ${verification.passed ? 'Passed' : 'Failed'} (${verification.score}/100)`;

    badge.appendChild(icon);
    badge.appendChild(label);

    if (verification.summary) {
      const summary = document.createElement('div');
      summary.className = 'badge-summary';
      summary.textContent = verification.summary;
      badge.appendChild(summary);
    }

    const lastMsg = chatContainer.querySelector('.chat-message-assistant:last-child .message-body');
    if (lastMsg) lastMsg.appendChild(badge);
  }

  init();
})();
