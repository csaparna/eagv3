// content.js
// PDF.js removed in favor of offline JSON

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'FILL_WORKDAY_FORM') {
        fillWorkdayForm(request.data)
            .then(() => sendResponse({ success: true }))
            .catch(err => {
                console.error('Workday Autofill Error:', err);
                sendResponse({ success: false, error: err.toString() });
            });
        return true; // Keep message channel open for async response
    }
});

function injectFloatingWidget() {
    if (document.getElementById('antigravity-autofill-widget')) return;

    const container = document.createElement('div');
    container.id = 'antigravity-autofill-widget';
    
    container.innerHTML = `
        <div class="antigravity-header">🚀 Antigravity Autofill</div>
        <div class="antigravity-body">
            <button id="antigravity-fill-btn" class="antigravity-btn">Auto-fill Resume</button>
            <div id="antigravity-status">Ready.</div>
        </div>
    `;

    document.body.appendChild(container);

    const fillBtn = document.getElementById('antigravity-fill-btn');
    const statusDiv = document.getElementById('antigravity-status');

    fillBtn.addEventListener('click', async () => {
        statusDiv.textContent = 'Reading JSON...';
        statusDiv.style.color = '#60a5fa';

        try {
            const res = await fetch(chrome.runtime.getURL('resume.json'));
            if (!res.ok) throw new Error("Could not find resume.json in extension directory.");
            
            const parsedData = await res.json();
            
            statusDiv.textContent = 'Filling Form...';
            fillWorkdayForm(parsedData).then(() => {
                statusDiv.textContent = 'Autofill Complete!';
                statusDiv.style.color = '#10b981';
                setTimeout(() => { statusDiv.textContent = 'Ready.'; statusDiv.style.color = '#f8fafc'; }, 5000);
            });
        } catch (err) {
            console.error(err);
            statusDiv.textContent = 'Error loading resume.json.';
            statusDiv.style.color = '#ef4444';
        }
    });
}

// Inject the widget onto the Workday page after a short delay
setTimeout(injectFloatingWidget, 1500);

function setReactInputValue(inputElement, value) {
    if (!inputElement) return;

    // React overrides the native value setter. We need to get the original setter to bypass React's tracking,
    // so that when we fire the 'input' event, React notices the change.
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value'
    ).set;
    const nativeTextAreaValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        'value'
    )?.set;

    if (inputElement.tagName === 'TEXTAREA' && nativeTextAreaValueSetter) {
        nativeTextAreaValueSetter.call(inputElement, value);
    } else if (nativeInputValueSetter) {
        nativeInputValueSetter.call(inputElement, value);
    } else {
        inputElement.value = value;
    }

    inputElement.dispatchEvent(new Event('input', { bubbles: true }));
    inputElement.dispatchEvent(new Event('change', { bubbles: true }));
    inputElement.dispatchEvent(new Event('blur', { bubbles: true }));
}

async function fillWorkdayForm(data) {
    // Fill Personal Info
    if (data.personal_info) {
        const info = data.personal_info;
        const firstNameInput = document.querySelector('[data-automation-id*="firstName" i], [data-automation-id*="legalNameFirst" i]');
        const lastNameInput = document.querySelector('[data-automation-id*="lastName" i], [data-automation-id*="legalNameLast" i]');
        const addressLine1Input = document.querySelector('[data-automation-id*="addressLine1" i]');
        const cityInput = document.querySelector('[data-automation-id*="city" i]');
        const stateInput = document.querySelector('[data-automation-id*="countryRegion" i], [data-automation-id*="state" i]');
        const postalCodeInput = document.querySelector('[data-automation-id*="postalCode" i]');
        const emailInput = document.querySelector('[data-automation-id*="email" i]');
        const phoneInput = document.querySelector('[data-automation-id*="phone" i], input[type="tel"]');

        if (firstNameInput) setReactInputValue(firstNameInput, info.firstName);
        if (lastNameInput) setReactInputValue(lastNameInput, info.lastName);
        if (addressLine1Input) setReactInputValue(addressLine1Input, info.addressLine1);
        if (cityInput) setReactInputValue(cityInput, info.city);
        if (stateInput) setReactInputValue(stateInput, info.state);
        if (postalCodeInput) setReactInputValue(postalCodeInput, info.postalCode);
        if (emailInput) setReactInputValue(emailInput, info.email);
        if (phoneInput) setReactInputValue(phoneInput, info.phone);
    }

    // Fill Experience
    if (data.experience && data.experience.length > 0) {
        // Workday typical selectors (can vary per deployment)
        const jobTitleInput = document.querySelector('[data-automation-id="jobTitle"]');
        const companyInput = document.querySelector('[data-automation-id="company"]');
        const locationInput = document.querySelector('[data-automation-id="location"]');
        const descriptionInput = document.querySelector('[data-automation-id="description"] textarea, textarea[data-automation-id="description"]');
        
        // Dates are usually split by Month/Year and Start/End in Workday.
        // It's often structured with containers or multiple matching attributes where the first is Start, second is End.
        const monthInputs = document.querySelectorAll('[data-automation-id="dateSectionMonth-input"]');
        const yearInputs = document.querySelectorAll('[data-automation-id="dateSectionYear-input"]');

        const exp = data.experience[0]; // Assuming filling the first item on the current form

        if (jobTitleInput) setReactInputValue(jobTitleInput, exp.title);
        if (companyInput) setReactInputValue(companyInput, exp.company);
        if (locationInput) setReactInputValue(locationInput, exp.location);
        if (descriptionInput) setReactInputValue(descriptionInput, exp.description);

        if (monthInputs.length > 0 && exp.startMonth) setReactInputValue(monthInputs[0], exp.startMonth);
        if (yearInputs.length > 0 && exp.startYear) setReactInputValue(yearInputs[0], exp.startYear);
        if (monthInputs.length > 1 && exp.endMonth) setReactInputValue(monthInputs[1], exp.endMonth);
        if (yearInputs.length > 1 && exp.endYear) setReactInputValue(yearInputs[1], exp.endYear);
    }

    // Fill Education
    if (data.education && data.education.length > 0) {
        const schoolInput = document.querySelector('[data-automation-id="school"]');
        const degreeInput = document.querySelector('[data-automation-id="degree"]');
        const majorInput = document.querySelector('[data-automation-id="fieldOfStudy"]');
        
        const edu = data.education[0]; // Assuming filling the first item on the current form container
        
        if (schoolInput) setReactInputValue(schoolInput, edu.school);
        if (degreeInput) setReactInputValue(degreeInput, edu.degree);
        if (majorInput) setReactInputValue(majorInput, edu.major);
    }

    // Note: To fully support multiple experiences, the script would need to click the "Add another" button and wait for the new form elements.
    console.log("Workday Autofill completed first entries. Multi-entry support requires user to click 'Add another' first or deeper DOM manipulation.");
}
