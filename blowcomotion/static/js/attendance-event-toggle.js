function toggleEventNameField() {
    const eventTypeSelect = document.getElementById('event_type');
    const eventNameField = document.getElementById('event_name_field');
    const eventNameInput = document.getElementById('event_name');
    
    if (eventTypeSelect && eventNameField && eventNameInput) {
        if (eventTypeSelect.value === 'performance') {
            eventNameField.style.display = 'block';
        } else {
            eventNameField.style.display = 'none';
            eventNameInput.value = ''; // Clear the field when hidden
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    toggleEventNameField();
});

// Also initialize after HTMX requests
document.body.addEventListener('htmx:afterSettle', function() {
    toggleEventNameField();
});
