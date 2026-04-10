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
    if (!inputElement || !value) return;

    // Make sure we are actually targeting an input, not a div wrapper
    if (inputElement.tagName !== 'INPUT' && inputElement.tagName !== 'TEXTAREA') {
        console.warn('Attempted to set value on non-input element:', inputElement);
        return;
    }

    // React overrides the native value setter. We need to get the original setter to bypass React's tracking,
    // so that when we fire the 'input' event, React notices the change.
    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value'
    )?.set;
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
    // Helper to safely extract input
    const extractInput = (el) => {
        if (!el) return null;
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return el;
        return el.querySelector('input, textarea');
    };

    const findInput = (selector, container = document) => {
        return extractInput(container.querySelector(selector));
    };
    
    const findInputs = (selector, container = document) => {
        return Array.from(container.querySelectorAll(selector)).map(extractInput).filter(Boolean);
    };

    // Robust human-like fallback finder
    const findByLabel = (container, textStr) => {
        const labels = Array.from(container.querySelectorAll('label'));
        for (let label of labels) {
            if (label.innerText.toLowerCase().includes(textStr.toLowerCase())) {
                const forAttr = label.getAttribute('for');
                if (forAttr) {
                    const el = document.getElementById(forAttr);
                    if (extractInput(el)) return extractInput(el);
                }
                if (extractInput(label)) return extractInput(label);
                
                let curr = label.nextElementSibling;
                while (curr) {
                    if (extractInput(curr)) return extractInput(curr);
                    curr = curr.nextElementSibling;
                }
                const parentSibling = label.parentElement?.nextElementSibling;
                if (parentSibling && extractInput(parentSibling)) return extractInput(parentSibling);
            }
        }
        return null;
    };

    // Fill Personal Info
    if (data.personal_info) {
        const info = data.personal_info;
        const firstNameInput = findInput('[data-automation-id*="firstName" i], [data-automation-id*="legalNameFirst" i]');
        const lastNameInput = findInput('[data-automation-id*="lastName" i], [data-automation-id*="legalNameLast" i]');
        const addressLine1Input = findInput('[data-automation-id*="addressLine1" i]');
        const cityInput = findInput('[data-automation-id*="city" i]');
        const stateInput = findInput('[data-automation-id*="countryRegion" i], [data-automation-id*="state" i]');
        const postalCodeInput = findInput('[data-automation-id*="postalCode" i]');
        const emailInput = findInput('[data-automation-id*="email" i], input[type="email"]');
        const phoneInput = findInput('[data-automation-id*="phone" i], input[type="tel"]');

        if (firstNameInput) setReactInputValue(firstNameInput, info.firstName);
        if (lastNameInput) setReactInputValue(lastNameInput, info.lastName);
        if (addressLine1Input) setReactInputValue(addressLine1Input, info.addressLine1);
        if (cityInput) setReactInputValue(cityInput, info.city);
        if (stateInput) setReactInputValue(stateInput, info.state);
        if (postalCodeInput) setReactInputValue(postalCodeInput, info.postalCode);
        if (emailInput) setReactInputValue(emailInput, info.email);
        if (phoneInput) setReactInputValue(phoneInput, info.phone);
    }

    // Fill Experience Block-by-Block
    if (data.experience && data.experience.length > 0) {
        const companyInputs = findInputs('[data-automation-id*="company" i]');
        
        for (let i = 0; i < Math.min(data.experience.length, companyInputs.length); i++) {
            const exp = data.experience[i];
            const companyInput = companyInputs[i];
            
            // Go up the tree to find the overarching Work Experience block container
            let block = companyInput.parentElement;
            while (block && block !== document.body) {
                // A reliable Work Experience block contains multiple distinct fields
                if (block.querySelector('label') && block.innerText.includes('Job Title')) break;
                block = block.parentElement;
            }
            if (!block || block === document.body) {
                 block = companyInput.closest('[data-automation-id*="workExperience" i]') || companyInput.parentElement.parentElement.parentElement.parentElement;
            }

            const titleIn = findInput('[data-automation-id*="jobTitle" i]', block) || findByLabel(block, 'job title');
            const compIn = companyInput; 
            const locIn = findInput('[data-automation-id*="location" i]', block) || findByLabel(block, 'location');
            const descIn = findInput('[data-automation-id*="description" i], textarea', block) || findByLabel(block, 'role description') || findByLabel(block, 'description');
            
            if (titleIn) setReactInputValue(titleIn, exp.title);
            if (compIn) setReactInputValue(compIn, exp.company);
            if (locIn) setReactInputValue(locIn, exp.location);
            if (descIn) setReactInputValue(descIn, exp.description);

            // current work
            const currIn = findInput('[data-automation-id*="currentlyWorkHere" i], [data-automation-id*="current" i][type="checkbox"], input[type="checkbox"]', block) || findByLabel(block, 'currently work here');
            if (currIn && currIn.type === 'checkbox') {
                const isCurrent = !exp.endYear || exp.endYear === "";
                if (isCurrent !== currIn.checked) currIn.click();
            }

            // dates
            const fromIn = findInput('[data-automation-id*="fromDate" i], [data-automation-id*="startDate" i]', block) || findByLabel(block, 'from');
            const toIn = findInput('[data-automation-id*="toDate" i], [data-automation-id*="endDate" i]', block) || findByLabel(block, 'to');
            const monthIn = findInputs('[data-automation-id*="Month" i]', block);
            const yearIn = findInputs('[data-automation-id*="Year" i]', block);

            if (fromIn) {
                const sDate = exp.startMonth ? `${exp.startMonth}${exp.startYear}` : exp.startYear;
                if (sDate) setReactInputValue(fromIn, sDate);
            } else if (monthIn[0] && yearIn[0]) {
                if (exp.startMonth) setReactInputValue(monthIn[0], exp.startMonth);
                if (exp.startYear) setReactInputValue(yearIn[0], exp.startYear);
            }

            if (toIn) {
                const eDate = exp.endMonth ? `${exp.endMonth}${exp.endYear}` : exp.endYear;
                if (eDate) setReactInputValue(toIn, eDate);
            } else if (monthIn.length > 1 && yearIn.length > 1) {
                if (exp.endMonth) setReactInputValue(monthIn[1], exp.endMonth);
                if (exp.endYear) setReactInputValue(yearIn[1], exp.endYear);
            }
        }
    }

    // Fill Education Block-by-Block
    if (data.education && data.education.length > 0) {
        const schoolInputs = findInputs('[data-automation-id*="school" i]');
        for (let i = 0; i < Math.min(data.education.length, schoolInputs.length); i++) {
            const edu = data.education[i];
            const schoolInput = schoolInputs[i];
            
            let block = schoolInput.parentElement;
            while (block && block !== document.body) {
                if (block.querySelector('label') && block.innerText.includes('Degree')) break;
                block = block.parentElement;
            }
            if (!block || block === document.body) {
                 block = schoolInput.closest('[data-automation-id*="education" i]') || schoolInput.parentElement.parentElement.parentElement.parentElement;
            }

            const degreeIn = findInput('[data-automation-id*="degree" i]', block) || findByLabel(block, 'degree');
            const majorIn = findInput('[data-automation-id*="fieldOfStudy" i], [data-automation-id*="major" i]', block) || findByLabel(block, 'field of study') || findByLabel(block, 'major');
            
            if (schoolInput) setReactInputValue(schoolInput, edu.school);
            if (degreeIn) setReactInputValue(degreeIn, edu.degree);
            if (majorIn) setReactInputValue(majorIn, edu.major);
        }
    }

    console.log("Workday Autofill completed multi-entries with robust block scoping and label matching.");
}
