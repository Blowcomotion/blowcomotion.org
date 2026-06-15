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
            // Use htmx:confirm to intercept before the request is made
            document.body.addEventListener('htmx:confirm', function(event) {
                var form = event.target;
                
                // Only handle forms that post to process-form
                var hxPost = form.getAttribute('hx-post') || '';
                if (hxPost.indexOf('process-form') === -1) {
                    return;
                }
                
                var tokenInput = form.querySelector('input[name="g-recaptcha-response"]');
                
                // If we already have a token, allow the request
                if (tokenInput && tokenInput.value) {
                    return;
                }
                
                // Prevent the request until we have a token
                event.preventDefault();
                
                grecaptcha.ready(function() {
                    grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                        if (tokenInput) {
                            tokenInput.value = token;
                        }
                        // Re-issue the request now that we have a token
                        event.detail.issueRequest(true);
                    }).catch(function(error) {
                        console.error('reCAPTCHA error:', error);
                        // Allow form to submit anyway - server will reject if token is required
                        event.detail.issueRequest(true);
                    });
                });
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