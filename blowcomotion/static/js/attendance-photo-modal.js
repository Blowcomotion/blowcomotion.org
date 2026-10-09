// Expand a member's photo using the site's shared image lightbox (#imageModal,
// see base.html + main.js) instead of a one-off modal. The larger rendition is
// fetched lazily on click rather than being generated for every member on
// every page load.
//
// Delegated on document, and guarded against double-registration, because
// HTMX re-renders (and re-executes <script> tags in) section_content.html
// every time a section is switched.
if (!window.__attendancePhotoModalBound) {
    window.__attendancePhotoModalBound = true;

    document.addEventListener('click', function(event) {
        const photo = event.target.closest('.attendance-member-photo');
        if (!photo) {
            return;
        }

        // Photos sit inside the member <label>; stop the click from also
        // toggling that member's attendance checkbox.
        event.preventDefault();
        event.stopPropagation();

        const memberId = photo.getAttribute('data-member-id');
        const memberName = photo.getAttribute('data-member-name') || '';
        if (!memberId) {
            return;
        }

        const $modal = jQuery('#imageModal');
        $modal.find('.modal-dialog').addClass('attendance-photo-modal-dialog');
        // This modal usually shows a multi-image carousel; hide those controls
        // since a member only has one photo.
        jQuery('#imageModalCounter, #imageModalPrev, #imageModalNext, #imageModalLink').hide();
        jQuery('#imageModalImg').attr('src', '').attr('alt', memberName);
        jQuery('#imageModalCaption').text(memberName).show();
        $modal.modal('show');

        fetch('/attendance/member-photo/' + encodeURIComponent(memberId) + '/')
            .then(function(response) {
                if (!response.ok) {
                    throw new Error('Photo request failed: ' + response.status);
                }
                return response.json();
            })
            .then(function(data) {
                jQuery('#imageModalImg').attr('src', data.url);
            })
            .catch(function(error) {
                console.error('Could not load member photo:', error);
                $modal.modal('hide');
            });
    });

    jQuery(document).on('hidden.bs.modal', '#imageModal', function() {
        jQuery(this).find('.modal-dialog').removeClass('attendance-photo-modal-dialog');
    });
}
