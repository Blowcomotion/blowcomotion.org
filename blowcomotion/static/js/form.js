(function ($) {
    $(document).ready(function() {
        // Set honeypot field value (spam protection)
        $('.best-color').val("purple");
        
        // reCAPTCHA v3 form handling
        // For HTMX forms, we need to get the token and add it to the request
        if (typeof grecaptcha !== 'undefined' && window.RECAPTCHA_SITE_KEY) {
            
            // Add hidden inputs and reCAPTCHA notice to all forms that post to process-form
            $('form[hx-post*="process-form"], form[action*="process-form"]').each(function() {
                var $form = $(this);
                
                if ($form.find('input[name="g-recaptcha-response"]').length === 0) {
                    $form.append('<input type="hidden" name="g-recaptcha-response" class="recaptcha-token" value="">');
                }
                
                // Add reCAPTCHA notice after submit buttons (required when hiding the badge)
                // Check if form already has a notice to avoid duplicates
                if ($form.find('.recaptcha-notice').length === 0) {
                    $form.append('<div class="recaptcha-notice" style="display: block; width: 100%; font-size: 0.75rem; color: #888; margin-top: 0.5rem; text-align: center;">This site is protected by reCAPTCHA.</div>');
                }
            });
            
            // Handle HTMX form submissions
            // Use htmx:configRequest to add token before every HTMX request
            document.body.addEventListener('htmx:configRequest', function(event) {
                var form = event.detail.elt;
                if (form.tagName !== 'FORM') {
                    form = form.closest('form');
                }
                if (!form) return;
                
                // Only handle forms that post to process-form
                var hxPost = form.getAttribute('hx-post') || '';
                if (hxPost.indexOf('process-form') === -1) {
                    return;
                }
                
                var tokenInput = form.querySelector('input[name="g-recaptcha-response"]');
                
                // If we have a token, add it to the request parameters
                if (tokenInput && tokenInput.value) {
                    event.detail.parameters['g-recaptcha-response'] = tokenInput.value;
                }
            });
            
            // Pre-fetch reCAPTCHA token on form focus for faster submission
            $('form[hx-post*="process-form"]').on('focusin', function() {
                var $form = $(this);
                var $tokenInput = $form.find('input[name="g-recaptcha-response"]');
                
                // Only fetch if we don't have a token yet
                if ($tokenInput.length && !$tokenInput.val()) {
                    grecaptcha.ready(function() {
                        grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                            $tokenInput.val(token);
                        });
                    });
                }
            });
            
            // Get fresh token right before HTMX submit
            $('form[hx-post*="process-form"]').on('submit', function(e) {
                var $form = $(this);
                var $tokenInput = $form.find('input[name="g-recaptcha-response"]');
                
                if ($tokenInput.length) {
                    // Get a fresh token synchronously if possible (token might be stale)
                    grecaptcha.ready(function() {
                        grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                            $tokenInput.val(token);
                        });
                    });
                }
            });
            
            // Handle regular (non-HTMX) form submissions
            $('form[action*="process-form"]').not('[hx-post]').on('submit', function(event) {
                var $form = $(this);
                var $tokenInput = $form.find('input[name="g-recaptcha-response"]');
                
                // If we already have a token, allow submission
                if ($tokenInput.length && $tokenInput.val()) {
                    return true;
                }
                
                // Prevent submission and get token
                event.preventDefault();
                
                // Add hidden input if not exists
                if ($tokenInput.length === 0) {
                    $form.append('<input type="hidden" name="g-recaptcha-response" value="">');
                    $tokenInput = $form.find('input[name="g-recaptcha-response"]');
                }
                
                grecaptcha.ready(function() {
                    grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                        $tokenInput.val(token);
                        // Submit the form
                        $form.off('submit').submit();
                    }).catch(function(error) {
                        console.error('reCAPTCHA error:', error);
                        // Allow form to submit anyway - server will handle validation
                        $form.off('submit').submit();
                    });
                });
                
                return false;
            });
        }
    });
})(jQuery);