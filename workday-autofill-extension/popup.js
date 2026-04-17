const autofillBtn = document.getElementById('autofillBtn');
const statusDiv = document.getElementById('status');

autofillBtn.addEventListener('click', async () => {
  setStatus('Loading resume.json...', 'status-loading');
  autofillBtn.disabled = true;

  try {
    const res = await fetch(chrome.runtime.getURL('resume.json'));
    if (!res.ok) throw new Error("Could not find resume.json in extension directory.");
    
    const extractedJSON = await res.json();
    
    setStatus('Sending data to Workday form...', 'status-loading');

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab) {
        throw new Error('No active tab found.');
    }

    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });
    } catch(err) {
        console.warn('Script execution warning:', err);
    }
    
    setTimeout(() => {
        chrome.tabs.sendMessage(tab.id, {
            action: 'FILL_WORKDAY_FORM',
            data: extractedJSON
        }, (response) => {
            if (chrome.runtime.lastError) {
               setStatus('Error: Could not connect to page. Are you on a Workday site?', 'status-error');
               autofillBtn.disabled = false;
               return;
            }
            if (response && response.success) {
               setStatus('Autofill complete! Please review the form.', 'status-success');
            } else {
               setStatus('Autofill finished but encountered warnings. Please review.', 'status-success');
            }
            autofillBtn.disabled = false;
        });
    }, 200);

  } catch (err) {
    console.error(err);
    setStatus('Error: ' + err.message, 'status-error');
    autofillBtn.disabled = false;
  }
});

function setStatus(text, className) {
  statusDiv.textContent = text;
  statusDiv.className = 'status-container ' + className;
}
