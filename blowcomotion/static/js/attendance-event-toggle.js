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
