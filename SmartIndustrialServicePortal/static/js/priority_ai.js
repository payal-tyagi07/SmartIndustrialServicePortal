document.addEventListener('DOMContentLoaded', () => {
    const titleInput = document.getElementById('title');
    const descInput = document.getElementById('description');
    const prioritySelect = document.getElementById('priority');
    const aiSuggestionBox = document.getElementById('ai-suggestion-box');
    const suggestionText = document.getElementById('ai-suggestion-text');
    const applyBtn = document.getElementById('ai-suggestion-apply');
    const draftBtn = document.getElementById('ai-draft-button');
    const categorySelect = document.getElementById('category');

    if (!titleInput || !descInput || !prioritySelect || !aiSuggestionBox) return;

    const criticalKeywords = ['fire', 'shock', 'spark', 'explosion', 'high voltage', 'toxic', 'gas leak', 'hazardous', 'safety barrier', 'injury', 'blackout', 'power failure', 'emergency', 'blast', 'boiler'];
    const highKeywords = ['leak', 'burst', 'server down', 'outage', 'crane malfunction', 'engine failure', 'broken', 'accident', 'offline', 'shut down'];
    const mediumKeywords = ['flickering', 'jam', 'ac not cooling', 'slow', 'noise', 'jammed', 'light', 'wiring'];
    const lowKeywords = ['dust', 'trash', 'cleaning', 'paint', 'coffee', 'housekeeping', 'dirty', 'maintenance'];

    function analyzeText() {
        const text = (titleInput.value + ' ' + descInput.value).toLowerCase();
        let suggestedPriority = '';

        // Match critical keywords first
        if (criticalKeywords.some(keyword => text.includes(keyword))) {
            suggestedPriority = 'Critical';
        } else if (highKeywords.some(keyword => text.includes(keyword))) {
            suggestedPriority = 'High';
        } else if (mediumKeywords.some(keyword => text.includes(keyword))) {
            suggestedPriority = 'Medium';
        } else if (lowKeywords.some(keyword => text.includes(keyword))) {
            suggestedPriority = 'Low';
        }

        if (suggestedPriority && suggestedPriority !== prioritySelect.value) {
            suggestionText.textContent = suggestedPriority;
            aiSuggestionBox.style.display = 'flex';
        } else {
            aiSuggestionBox.style.display = 'none';
        }
    }

    // Bind event listeners
    titleInput.addEventListener('input', analyzeText);
    descInput.addEventListener('input', analyzeText);
    prioritySelect.addEventListener('change', () => {
        aiSuggestionBox.style.display = 'none';
    });

    if (applyBtn) {
        applyBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const value = suggestionText.textContent;
            prioritySelect.value = value;
            aiSuggestionBox.style.display = 'none';
            
            // Add flash visual feedback to the select element
            prioritySelect.style.outline = '2px solid var(--info)';
            setTimeout(() => {
                prioritySelect.style.outline = 'none';
            }, 1000);
        });
    }

    function titleCase(value) {
        return value.replace(/\s+/g, ' ').trim().replace(/\b\w/g, letter => letter.toUpperCase());
    }

    function buildDescriptionDraft() {
        const title = titleInput.value.trim();
        if (!title) {
            titleInput.focus();
            titleInput.setCustomValidity('Enter a complaint title before generating a draft.');
            titleInput.reportValidity();
            titleInput.setCustomValidity('');
            return;
        }

        const category = categorySelect && categorySelect.value ? categorySelect.value : 'service request';
        const draft = `Issue reported: ${titleCase(title)}.\n\nLocation: [Enter the exact plant / building / floor / area]\n\nEquipment / asset / serial number: [Enter equipment name and serial number, if available]\n\nObserved symptoms: [Describe what is happening, when it started, any error messages, sounds, leaks, damage, or safety concerns]\n\nOperational impact: [State whether work is stopped, delayed, or affected]\n\nRequested assistance: Please inspect and resolve this ${category.toLowerCase()} issue.`;

        if (descInput.value.trim() && !window.confirm('Replace the current description with a new AI draft?')) {
            return;
        }

        descInput.value = draft;
        descInput.focus();
        analyzeText();
    }

    if (draftBtn) {
        draftBtn.addEventListener('click', buildDescriptionDraft);
    }
});
