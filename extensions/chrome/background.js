const API = 'http://127.0.0.1:8765/api/capture';

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'qc-capture',
    title: 'Quick capture to workbench',
    contexts: ['selection', 'link', 'page']
  });
});

function notify(title, message) {
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon.png',
    title: title,
    message: message
  });
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== 'qc-capture') return;
  const selection = (info.selectionText || '').trim();
  const title = (selection || info.linkText || (tab && tab.title) || '').trim().slice(0, 120);
  if (!title) {
    notify('Quick capture', 'Nothing to capture');
    return;
  }
  const payload = {
    title: title,
    content: selection,
    url: info.linkUrl || info.pageUrl || (tab && tab.url) || '',
    source: 'browser-context-menu'
  };
  try {
    const res = await fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.duplicate) {
      notify('Quick capture', 'Duplicate skipped');
    } else if (data.dry_run) {
      notify('Quick capture', 'DRY-RUN: not written to Feishu');
    } else {
      notify('Quick capture', 'Saved: ' + (data.record_id || 'ok'));
    }
  } catch (e) {
    notify('Quick capture', 'Service offline: start python server.py');
  }
});
