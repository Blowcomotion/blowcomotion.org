console.log('Attendance event toggle script loaded');

function toggleEventNameField() {
    const eventTypeRadios = document.querySelectorAll('input[name="event_type"]');
    const eventNameField = document.getElementById('event_name_field');
    const eventNameInput = document.getElementById('event_name');
    
    if (eventTypeRadios.length > 0 && eventNameField && eventNameInput) {
        const selectedEventType = document.querySelector('input[name="event_type"]:checked');
        if (selectedEventType && selectedEventType.value === 'performance') {
            eventNameField.style.display = 'block';
        } else {
            eventNameField.style.display = 'none';
            // Don't clear the field value to maintain persistence
        }
    }
}

function updateAttendanceCheckmarks() {
    const dateField = document.getElementById('attendance_date');
    
    if (dateField && dateField.value) {
        const selectedDate = dateField.value;
        
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
    toggleEventNameField();
    
    // Add event listener for date changes
    const dateField = document.getElementById('attendance_date');
    if (dateField) {
        dateField.addEventListener('change', updateAttendanceCheckmarks);
    }
});

// Also initialize after HTMX requests
document.body.addEventListener('htmx:afterSettle', function() {
    toggleEventNameField();
    
    // Re-add event listener for date changes after HTMX updates
    const dateField = document.getElementById('attendance_date');
    if (dateField) {
        dateField.removeEventListener('change', updateAttendanceCheckmarks);
        dateField.addEventListener('change', updateAttendanceCheckmarks);
    }
});
