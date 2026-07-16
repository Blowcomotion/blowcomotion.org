(function ($) {
    // Forms that go through the shared public-form pipeline, or the member
    // portal's plain-POST forms.
    var FORM_SELECTOR = 'form[hx-post*="process-form"], form[action*="process-form"], form#member-form, form[data-recaptcha]';

    // Disable the submit button and relabel it while a submission is in
    // flight, so a slow response (e.g. a stalled SMTP send) can't be
    // mistaken for a failed submit and re-clicked, creating duplicates.
    function markSubmitting($form) {
        var $btn = $form.find('button[type="submit"]').first();
        if ($btn.length === 0 || $btn.prop('disabled')) return;
        $btn.data('original-text', $btn.text());
        $btn.prop('disabled', true).text('Sending...');
    }

    // Restore the button so the form can be resubmitted after an error.
    // Not needed on the plain-POST path: the browser navigates away on submit.
    function clearSubmitting($form) {
        var $btn = $form.find('button[type="submit"]').first();
        if ($btn.length === 0) return;
        var original = $btn.data('original-text');
        if (original !== undefined) {
            $btn.text(original);
        }
        $btn.prop('disabled', false);
    }

    $(document).ready(function() {
        // Plain (non-HTMX) forms: the browser navigates away on submit, so
        // only disabling is needed. Bound directly (matching how the
        // reCAPTCHA handler below binds) and registered first, so it runs
        // before that handler's `return false` can stop propagation.
        $(FORM_SELECTOR).not('[hx-post]').on('submit', function() {
            markSubmitting($(this));
        });

        // HTMX forms: htmx does not disable buttons on its own. Disable as
        // soon as the request starts and re-enable once it completes, in
        // case the response leaves the form in place (e.g. a validation error).
        document.body.addEventListener('htmx:beforeRequest', function(event) {
            var form = event.detail.elt;
            if (form.tagName !== 'FORM') form = form.closest('form');
            if (!form || !$(form).is(FORM_SELECTOR)) return;
            markSubmitting($(form));
        });

        document.body.addEventListener('htmx:afterRequest', function(event) {
            var form = event.detail.elt;
            if (form.tagName !== 'FORM') form = form.closest('form');
            if (!form || !$(form).is(FORM_SELECTOR)) return;
            clearSubmitting($(form));
        });

        // reCAPTCHA disclosure notice (required when hiding the badge)
        $('form[hx-post*="process-form"], form[action*="process-form"], form#member-form, form[data-recaptcha]').each(function() {
            var $form = $(this);
            if ($form.find('.recaptcha-notice').length === 0) {
                $form.append('<div class="recaptcha-notice" style="display: block; width: 100%; font-size: 0.75rem; color: #888; margin-top: 0.5rem; text-align: center;">This site is protected by reCAPTCHA.</div>');
            }
        });

        // reCAPTCHA v3 token injection and form handling
        if (typeof grecaptcha !== 'undefined' && window.RECAPTCHA_SITE_KEY) {

            // Add hidden token inputs to all reCAPTCHA-protected forms
            $('form[hx-post*="process-form"], form[action*="process-form"], form#member-form, form[data-recaptcha]').each(function() {
                var $form = $(this);
                if ($form.find('input[name="g-recaptcha-response"]').length === 0) {
                    $form.append('<input type="hidden" name="g-recaptcha-response" class="recaptcha-token" value="">');
                }
            });
            
            // Handle HTMX form submissions
            // Use htmx:beforeRequest to cancel request if no token, fetch token, then retry
            document.body.addEventListener('htmx:beforeRequest', function(event) {
                var form = event.detail.elt;
                if (form.tagName !== 'FORM') {
                    form = form.closest('form');
                }
                if (!form) return;
                
                // If a previous reCAPTCHA attempt failed, allow one request to proceed to avoid a retry loop
                if (form.dataset.recaptchaBypass === '1') {
                    delete form.dataset.recaptchaBypass;
                    return;
                }
                
                // Only handle forms that post to process-form
                var hxPost = form.getAttribute('hx-post') || '';
                if (hxPost.indexOf('process-form') === -1) {
                    return;
                }
                
                var tokenInput = form.querySelector('input[name="g-recaptcha-response"]');
                
                // Create token input if it doesn't exist (for dynamically injected forms)
                if (!tokenInput) {
                    tokenInput = document.createElement('input');
                    tokenInput.type = 'hidden';
                    tokenInput.name = 'g-recaptcha-response';
                    form.appendChild(tokenInput);
                }
                
                // If we already have a recent token (reCAPTCHA v3 tokens are valid ~2min), allow request
                if (tokenInput.value && tokenInput.dataset.tokenTime) {
                    var tokenAge = Date.now() - parseInt(tokenInput.dataset.tokenTime, 10);
                    if (tokenAge < 110000) {  // ~110s (keeps buffer under Google's ~2min lifetime)
                        // Recent token, proceed with request
                        return;
                    }
                }
                
                // Cancel this request, get a fresh token, then re-trigger
                event.preventDefault();
                
                grecaptcha.ready(function() {
                    grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                        tokenInput.value = token;
                        tokenInput.dataset.tokenTime = Date.now().toString();
                        // Re-trigger the HTMX request now that we have a token
                        htmx.trigger(form, 'submit');
                    }).catch(function(error) {
                        console.error('reCAPTCHA error:', error);
                        // Avoid retry loops: allow one request to proceed without a token (server will decide)
                        form.dataset.recaptchaBypass = '1';
                        htmx.trigger(form, 'submit');
                    });
                });
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
                            $tokenInput.attr('data-token-time', Date.now().toString());
                        });
                    });
                }
            });
            
            // Handle regular (non-HTMX) form submissions
            $('form[action*="process-form"], form#member-form, form[data-recaptcha]').not('[hx-post]').on('submit', function(event) {
                var $form = $(this);
                var $tokenInput = $form.find('input[name="g-recaptcha-response"]');
                
                // Check if we have a recent token (reCAPTCHA v3 tokens expire in ~2 minutes)
                if ($tokenInput.length && $tokenInput.val()) {
                    var tokenTime = $tokenInput.attr('data-token-time');
                    if (tokenTime) {
                        var tokenAge = Date.now() - parseInt(tokenTime, 10);
                        if (tokenAge < 110000) {  // ~110s (keeps buffer under Google's ~2min lifetime)
                            return true;  // Recent token, allow submission
                        }
                    } else {
                        return true;  // Token exists but no timestamp, allow submission
                    }
                }
                
                // Prevent submission and get fresh token
                event.preventDefault();
                
                // Add hidden input if not exists
                if ($tokenInput.length === 0) {
                    $form.append('<input type="hidden" name="g-recaptcha-response" value="">');
                    $tokenInput = $form.find('input[name="g-recaptcha-response"]');
                }
                
                grecaptcha.ready(function() {
                    grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: 'submit'}).then(function(token) {
                        $tokenInput.val(token);
                        $tokenInput.attr('data-token-time', Date.now().toString());
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