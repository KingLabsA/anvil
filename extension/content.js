// Anvil Browser Extension - Content Script

// Inject Anvil button into code blocks
function injectAnvilButton() {
  const codeBlocks = document.querySelectorAll('pre code, pre, code');
  
  codeBlocks.forEach((codeBlock) => {
    // Skip if already injected
    if (codeBlock.dataset.anvilInjected) return;
    
    // Check if it looks like code
    const text = codeBlock.textContent.trim();
    if (text.length < 10) return;
    
    // Mark as injected
    codeBlock.dataset.anvilInjected = 'true';
    
    // Create wrapper
    const wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    wrapper.style.marginTop = '8px';
    
    // Create button
    const button = document.createElement('button');
    button.textContent = '🔨 Ask Anvil';
    button.style.cssText = `
      background: #f59e0b;
      color: #0a0a0a;
      border: none;
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      margin-top: 8px;
      transition: background 0.2s;
    `;
    
    button.addEventListener('mouseenter', () => {
      button.style.background = '#d97706';
    });
    
    button.addEventListener('mouseleave', () => {
      button.style.background = '#f59e0b';
    });
    
    button.addEventListener('click', () => {
      // Send message to background script
      chrome.runtime.sendMessage({
        action: 'openPopupWithCode',
        code: text
      });
    });
    
    // Insert button after code block
    codeBlock.parentNode.insertBefore(wrapper, codeBlock.nextSibling);
    wrapper.appendChild(button);
  });
}

// Run on page load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', injectAnvilButton);
} else {
  injectAnvilButton();
}

// Watch for dynamically added code blocks
const observer = new MutationObserver((mutations) => {
  mutations.forEach((mutation) => {
    if (mutation.addedNodes.length > 0) {
      injectAnvilButton();
    }
  });
});

observer.observe(document.body, {
  childList: true,
  subtree: true
});

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getSelectedCode') {
    const selection = window.getSelection();
    sendResponse({ code: selection.toString() });
  }
});
