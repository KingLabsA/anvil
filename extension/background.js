// Anvil Browser Extension - Background Service Worker

// Create context menu
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'anvil-explain',
    title: 'Anvil: Explain Code',
    contexts: ['selection']
  });

  chrome.contextMenus.create({
    id: 'anvil-optimize',
    title: 'Anvil: Optimize Code',
    contexts: ['selection']
  });

  chrome.contextMenus.create({
    id: 'anvil-review',
    title: 'Anvil: Review Code',
    contexts: ['selection']
  });

  chrome.contextMenus.create({
    id: 'anvil-fix',
    title: 'Anvil: Fix Issues',
    contexts: ['selection']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const selectedText = info.selectionText;
  
  const prompts = {
    'anvil-explain': 'Explain this code in simple terms:',
    'anvil-optimize': 'Optimize this code for performance and readability:',
    'anvil-review': 'Review this code for bugs, security issues, and best practices:',
    'anvil-fix': 'Fix any issues in this code:'
  };

  const prompt = prompts[info.menuItemId];
  const query = `${prompt}\n\n\`\`\`\n${selectedText}\n\`\`\``;

  // Open popup with pre-filled query
  chrome.action.openPopup();
  
  // Store query for popup to retrieve
  chrome.storage.local.set({ pendingQuery: query });
});

// Handle messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getPendingQuery') {
    chrome.storage.local.get(['pendingQuery'], (result) => {
      sendResponse({ query: result.pendingQuery || '' });
      // Clear after retrieving
      chrome.storage.local.remove(['pendingQuery']);
    });
    return true; // Keep message channel open for async response
  }
});

// Keep service worker alive
chrome.runtime.onStartup.addListener(() => {
  console.log('Anvil extension started');
});
