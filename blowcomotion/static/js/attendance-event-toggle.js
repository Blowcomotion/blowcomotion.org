// Cache for gig options by date
let gigOptionsCache = {};
let updateGigOptionsTimeout = null;
let currentGigRequest = null;

function updateGigOptions() {
    const dateField = document.getElementById('attendance_date');
    
    if (!dateField || !dateField.value) {
        console.log('No date field or value');
        return;
    }
    
    const selectedDate = dateField.value;
    console.log('Updating gig options for date:', selectedDate);
    
    // Check cache first
    if (gigOptionsCache[selectedDate]) {
        console.log('Using cached gigs for', selectedDate);
        populateGigRadios(gigOptionsCache[selectedDate]);
        return;
    }
    
    // Cancel any pending request
    if (currentGigRequest) {
        console.log('Cancelling previous request');
        currentGigRequest.abort();
        currentGigRequest = null;
    }
    
    // Debounce the API call
    if (updateGigOptionsTimeout) {
        clearTimeout(updateGigOptionsTimeout);
    }
    
    updateGigOptionsTimeout = setTimeout(() => {
        console.log('Fetching gigs from API for', selectedDate);
        
        // Create AbortController for this request
        const controller = new AbortController();
        currentGigRequest = controller;
        
        fetch(`/attendance/gigs-for-date/?date=${selectedDate}`, {
            signal: controller.signal
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Received gigs data:', data);
                // Cache the result
                gigOptionsCache[selectedDate] = data;
                populateGigRadios(data);
                currentGigRequest = null;
            })
            .catch(error => {
                if (error.name === 'AbortError') {
                    console.log('Request was aborted');
                } else {
                    console.error('Error fetching gigs:', error);
                }
                currentGigRequest = null;
            });
    }, 300); // 300ms debounce
}

function populateGigRadios(data) {
    // Find the specific event type container by looking for the rehearsal radio
    const rehearsalRadio = document.getElementById('event_type_rehearsal');
    if (!rehearsalRadio) {
        console.log('Rehearsal radio not found');
        return;
    }
    
    // Get the parent container of all radio buttons
    const eventTypeContainer = rehearsalRadio.closest('.mb-3');
    if (!eventTypeContainer) {
        console.log('Event type container not found');
        return;
    }
    
    // Remove all existing gig radio buttons and performance_no_gig
    const allRadios = eventTypeContainer.querySelectorAll('.form-check');
    allRadios.forEach(radioDiv => {
        const input = radioDiv.querySelector('input[type="radio"]');
        if (input && (input.value.startsWith('gig_') || input.value === 'performance_no_gig')) {
            radioDiv.remove();
        }
    });
    
    // Check if any radio was previously selected (before we removed gig radios)
    const currentlySelected = eventTypeContainer.querySelector('input[type="radio"]:checked');
    const wasGigSelected = !currentlySelected; // If nothing is checked now, a gig was selected before
    
    // Add new gig radio buttons or performance_no_gig option
    let firstGigRadio = null;
    let lastInsertedElement = rehearsalRadio.parentElement;
    
    if (data.gigs && data.gigs.length > 0) {
        console.log(`Adding ${data.gigs.length} gig(s) to radio buttons`);
        // Add individual gig radio buttons
        data.gigs.forEach((gig, index) => {
            const radioDiv = document.createElement('div');
            radioDiv.className = 'form-check';
            
            const radioInput = document.createElement('input');
            radioInput.className = 'form-check-input';
            radioInput.type = 'radio';
            radioInput.name = 'event_type';
            radioInput.id = `event_type_gig_${gig.id}`;
            radioInput.value = `gig_${gig.id}`;
            radioInput.required = true;
            
            const radioLabel = document.createElement('label');
            radioLabel.className = 'form-check-label';
            radioLabel.htmlFor = `event_type_gig_${gig.id}`;
            radioLabel.textContent = gig.title;
            
            radioDiv.appendChild(radioInput);
            radioDiv.appendChild(radioLabel);
            
            // Insert after the last inserted element to maintain order
            lastInsertedElement.insertAdjacentElement('afterend', radioDiv);
            lastInsertedElement = radioDiv;
            
            if (index === 0) {
                firstGigRadio = radioInput;
            }
        });
    } else {
        console.log('No gigs available, adding performance_no_gig option');
        // No gigs available, add the performance_no_gig option
        const radioDiv = document.createElement('div');
        radioDiv.className = 'form-check';
        
        const radioInput = document.createElement('input');
        radioInput.className = 'form-check-input';
        radioInput.type = 'radio';
        radioInput.name = 'event_type';
        radioInput.id = 'event_type_performance_no_gig';
        radioInput.value = 'performance_no_gig';
        radioInput.required = true;
        
        const radioLabel = document.createElement('label');
        radioLabel.className = 'form-check-label';
        radioLabel.htmlFor = 'event_type_performance_no_gig';
        radioLabel.textContent = 'Performance (no gig scheduled)';
        
        radioDiv.appendChild(radioInput);
        radioDiv.appendChild(radioLabel);
        
        // Insert after the rehearsal radio
        lastInsertedElement.insertAdjacentElement('afterend', radioDiv);
    }
    
    // Determine what should be selected after update
    if (wasGigSelected || !currentlySelected) {
        // Previously selected gig is no longer available or nothing was selected
        if (firstGigRadio) {
            // Select the first new gig
            firstGigRadio.checked = true;
            console.log('Selected first gig:', firstGigRadio.value);
        } else {
            // No gigs available, select rehearsal
            rehearsalRadio.checked = true;
            console.log('Selected rehearsal (no gigs available)');
        }
    } else {
        // Keep the current selection (rehearsal is still checked)
        console.log('Keeping current selection:', currentlySelected ? currentlySelected.value : 'none');
    }
}

function updateAttendanceCheckmarks() {
    const dateField = document.getElementById('attendance_date');
    
    if (dateField && dateField.value) {
        const selectedDate = dateField.value;
        
        // Update gig options when date changes
        updateGigOptions();
        
        // Since HTMX loads section content dynamically without changing URL,
        // we need to check if section-specific content is currently loaded
        const membersSection = document.getElementById('members-section');
        const isSectionContentLoaded = membersSection !== null;
        
        // Try to determine which section is currently active
        let sectionUrl = null;
        if (isSectionContentLoaded) {
            // Look for active section button to determine current section
            const activeButton = document.querySelector('.btn-group .btn-primary');
            if (activeButton && activeButton.href) {
                sectionUrl = new URL(activeButton.href).pathname;
            }
            // Alternative: check if there's a form action that indicates the section
            const form = document.querySelector('form[method="post"]');
            if (form && form.action) {
                const formUrl = new URL(form.action);
                if (formUrl.pathname !== '/attendance/') {
                    sectionUrl = formUrl.pathname;
                }
            }
        }
        
        if (isSectionContentLoaded && sectionUrl) {
            // Use HTMX to refresh only the members section with the new date's data
            if (window.htmx) {
                const requestUrl = sectionUrl + `?attendance_date=${selectedDate}`;
                htmx.ajax('GET', requestUrl, {
                    target: '#members-section', // Target just the members section
                    swap: 'innerHTML'
                });
            }
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Pre-fetch gigs for the current date if we have one
    const dateField = document.getElementById('attendance_date');
    if (dateField && dateField.value) {
        updateGigOptions();
    }
    
    // Add event listener for date changes
    if (dateField) {
        dateField.addEventListener('change', function() {
            updateAttendanceCheckmarks();
        });
    }
});

// Also initialize after HTMX requests
document.body.addEventListener('htmx:afterSettle', function() {
    // Pre-fetch gigs for the current date if we have one
    const dateField = document.getElementById('attendance_date');
    if (dateField && dateField.value) {
        updateGigOptions();
    }
    
    // Re-add event listener for date changes after HTMX updates
    if (dateField) {
        dateField.removeEventListener('change', updateAttendanceCheckmarks);
        dateField.addEventListener('change', function() {
            updateAttendanceCheckmarks();
        });
    }
});
