// Anvil Browser Extension - Popup Script

const API_BASE = 'http://localhost:8000';

// DOM Elements
const statusEl = document.getElementById('status');
const queryEl = document.getElementById('query');
const submitBtn = document.getElementById('submit');
const responseSection = document.getElementById('response');
const responseContent = document.getElementById('response-content');
const copyBtn = document.getElementById('copy');
const explainBtn = document.getElementById('explain');
const optimizeBtn = document.getElementById('optimize');
const reviewBtn = document.getElementById('review');
const settingsBtn = document.getElementById('settings');

// Check connection status
async function checkConnection() {
  try {
    const response = await fetch(`${API_BASE}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000)
    });
    
    if (response.ok) {
      statusEl.textContent = '●';
      statusEl.classList.remove('disconnected');
      submitBtn.disabled = false;
    } else {
      throw new Error('Server not responding');
    }
  } catch (error) {
    statusEl.textContent = '●';
    statusEl.classList.add('disconnected');
    submitBtn.disabled = true;
    showResponse('⚠️ Cannot connect to Anvil server.\n\nMake sure Anvil is running on localhost:8000\n\nRun: anvil serve');
  }
}

// Show response
function showResponse(text) {
  responseSection.style.display = 'flex';
  responseContent.textContent = text;
}

// Submit query
async function submitQuery() {
  const query = queryEl.value.trim();
  if (!query) return;

  submitBtn.disabled = true;
  submitBtn.textContent = 'Thinking...';
  
  try {
    const response = await fetch(`${API_BASE}/api/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        task: query,
        model: 'local',
        max_iterations: 20
      })
    });

    const data = await response.json();
    
    if (data.success) {
      showResponse(data.output || 'Task completed successfully');
    } else {
      showResponse(`Error: ${data.error || 'Unknown error'}`);
    }
  } catch (error) {
    showResponse(`Error: ${error.message}`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Ask Anvil';
  }
}

// Quick actions
async function quickAction(action) {
  // Get selected text from active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  let context = '';
  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const selection = window.getSelection();
        return selection.toString() || '';
      }
    });
    context = result.result;
  } catch (error) {
    // Ignore errors
  }

  const prompts = {
    explain: 'Explain this code in simple terms:',
    optimize: 'Optimize this code for performance and readability:',
    review: 'Review this code for bugs, security issues, and best practices:'
  };

  const prompt = prompts[action];
  if (context) {
    queryEl.value = `${prompt}\n\n\`\`\`\n${context}\n\`\`\``;
  } else {
    queryEl.value = prompt;
  }
  
  submitQuery();
}

// Copy response
function copyResponse() {
  const text = responseContent.textContent;
  navigator.clipboard.writeText(text).then(() => {
    copyBtn.textContent = '✓';
    setTimeout(() => {
      copyBtn.textContent = '📋';
    }, 2000);
  });
}

// Open settings
function openSettings() {
  chrome.runtime.openOptionsPage();
}

// Event listeners
submitBtn.addEventListener('click', submitQuery);
copyBtn.addEventListener('click', copyResponse);
explainBtn.addEventListener('click', () => quickAction('explain'));
optimizeBtn.addEventListener('click', () => quickAction('optimize'));
reviewBtn.addEventListener('click', () => quickAction('review'));
settingsBtn.addEventListener('click', openSettings);

// Enter to submit
queryEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    submitQuery();
  }
});

// Initialize
checkConnection();
setInterval(checkConnection, 5000); // Check every 5 seconds
