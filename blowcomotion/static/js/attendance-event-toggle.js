console.log('Attendance event toggle script loaded');

// Cache and debouncing variables
let gigOptionsCache = {};
let updateGigOptionsTimeout = null;
let currentGigRequest = null;

function toggleGigField() {
    const eventTypeRadios = document.querySelectorAll('input[name="event_type"]');
    const gigField = document.getElementById('gig_field');
    const gigSelect = document.getElementById('gig');
    const notesField = document.getElementById('notes_field');
    
    if (eventTypeRadios.length > 0 && gigField && gigSelect) {
        const selectedEventType = document.querySelector('input[name="event_type"]:checked');
        if (selectedEventType && selectedEventType.value === 'performance') {
            gigField.style.display = 'block';
            // Hide notes field initially for performance, will show if no gigs
            if (notesField) {
                notesField.style.display = 'none';
            }
            // When switching to performance, update gig options based on current date
            updateGigOptions();
        } else {
            gigField.style.display = 'none';
            // Show notes field for rehearsals
            if (notesField) {
                notesField.style.display = 'block';
            }
            // Don't clear the field value to maintain persistence
        }
    }
}

function updateGigOptions() {
    const dateField = document.getElementById('attendance_date');
    const gigSelect = document.getElementById('gig');
    
    if (!dateField || !gigSelect || !dateField.value) {
        return;
    }
    
    const selectedDate = dateField.value;
    
    // Check cache first
    if (gigOptionsCache[selectedDate]) {
        populateGigSelect(gigSelect, gigOptionsCache[selectedDate]);
        return;
    }
    
    // Cancel any pending request
    if (currentGigRequest) {
        currentGigRequest.abort();
        currentGigRequest = null;
    }
    
    // Debounce the API call
    if (updateGigOptionsTimeout) {
        clearTimeout(updateGigOptionsTimeout);
    }
    
    updateGigOptionsTimeout = setTimeout(() => {
        
        // Show loading indicator
        gigSelect.innerHTML = '<option value="">Loading gigs...</option>';
        gigSelect.disabled = true;
        
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
                // Cache the result
                gigOptionsCache[selectedDate] = data;
                populateGigSelect(gigSelect, data);
                gigSelect.disabled = false;
                currentGigRequest = null;
            })
            .catch(error => {
                if (error.name === 'AbortError') {
                    console.log('Gig request was cancelled');
                } else {
                    console.error('Error fetching gigs:', error);
                    gigSelect.innerHTML = '<option value="">Error loading gigs</option>';
                }
                gigSelect.disabled = false;
                currentGigRequest = null;
            });
    }, 300); // 300ms debounce
}

function populateGigSelect(gigSelect, data) {
    const notesField = document.getElementById('notes_field');
    const selectedEventType = document.querySelector('input[name="event_type"]:checked');
    
    // Clear existing options
    gigSelect.innerHTML = '<option value="">No specific gig selected</option>';
    
    let hasGigs = false;
    
    // Add gig options
    if (data.gigs && data.gigs.length > 0) {
        hasGigs = true;
        data.gigs.forEach(gig => {
            const option = document.createElement('option');
            option.value = gig.id;
            option.textContent = `${gig.date} - ${gig.title}`;
            gigSelect.appendChild(option);
        });
    } else {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No gigs scheduled for this date';
        gigSelect.appendChild(option);
    }
    
    // Show/hide notes field based on gig availability and event type
    if (notesField && selectedEventType) {
        if (selectedEventType.value === 'performance') {
            if (hasGigs) {
                // Hide notes field when gigs are available for performance
                notesField.style.display = 'none';
            } else {
                // Show notes field when no gigs are available for performance
                notesField.style.display = 'block';
            }
        } else {
            // Show notes field for rehearsals
            notesField.style.display = 'block';
        }
    }
}

function updateAttendanceCheckmarks() {
    const dateField = document.getElementById('attendance_date');
    
    if (dateField && dateField.value) {
        const selectedDate = dateField.value;
        
        // Always update gig options when date changes, even if performance isn't selected
        // This ensures the dropdown is ready when users switch to performance mode
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
    toggleGigField();
    
    // Pre-fetch gigs for the current date if we have one
    const dateField = document.getElementById('attendance_date');
    if (dateField && dateField.value) {
        updateGigOptions();
    }
    
    // Add event listener for date changes
    if (dateField) {
        dateField.addEventListener('change', function() {
            updateAttendanceCheckmarks();
            // Don't call updateGigOptions here separately as updateAttendanceCheckmarks already calls it
        });
    }
    
    // Add event listeners for event type changes
    const eventTypeRadios = document.querySelectorAll('input[name="event_type"]');
    eventTypeRadios.forEach(radio => {
        radio.addEventListener('change', toggleGigField);
    });
});

// Also initialize after HTMX requests
document.body.addEventListener('htmx:afterSettle', function() {
    toggleGigField();
    
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
            // Don't call updateGigOptions here separately as updateAttendanceCheckmarks already calls it
        });
    }
    
    // Re-add event listeners for event type changes after HTMX updates
    const eventTypeRadios = document.querySelectorAll('input[name="event_type"]');
    eventTypeRadios.forEach(radio => {
        radio.removeEventListener('change', toggleGigField);
        radio.addEventListener('change', toggleGigField);
    });
});
