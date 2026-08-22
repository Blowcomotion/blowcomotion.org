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

    // Boosted navigation (header nav, member portal sidebar) swaps whole
    // pages into <main> after this script's $(document).ready has already
    // run, so any binding here needs to reach forms that don't exist yet.
    // Delegating to $(document) covers those without re-binding on every swap.
    var PLAIN_FORM_SELECTOR = FORM_SELECTOR.split(', ').map(function (sel) {
        return sel + ':not([hx-post])';
    }).join(', ');

    function initRecaptchaUi(root) {
        // reCAPTCHA disclosure notice (required when hiding the badge)
        $(FORM_SELECTOR, root).each(function() {
            var $form = $(this);
            if ($form.find('.recaptcha-notice').length === 0) {
                $form.append('<div class="recaptcha-notice" style="display: block; width: 100%; font-size: 0.75rem; color: #888; margin-top: 0.5rem; text-align: center;">This site is protected by reCAPTCHA.</div>');
            }
        });

        if (typeof grecaptcha === 'undefined' || !window.RECAPTCHA_SITE_KEY) return;

        // Add hidden token inputs to all reCAPTCHA-protected forms
        $(FORM_SELECTOR, root).each(function() {
            var $form = $(this);
            if ($form.find('input[name="g-recaptcha-response"]').length === 0) {
                $form.append('<input type="hidden" name="g-recaptcha-response" class="recaptcha-token" value="">');
            }
        });
    }

    $(document).ready(function() {
        // Plain (non-HTMX) forms: the browser navigates away on submit, so
        // only disabling is needed. Delegated (matching how the reCAPTCHA
        // handler below binds) and registered first, so it runs before
        // that handler's `return false` can stop propagation.
        $(document).on('submit', PLAIN_FORM_SELECTOR, function() {
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

        initRecaptchaUi(document);

        // Boosted navigation swaps a fresh page into <main> without a
        // document.ready, so re-run the notice/token-input setup for
        // whatever just landed there.
        document.body.addEventListener('htmx:afterSwap', function(event) {
            initRecaptchaUi(event.detail.target);
        });

        // reCAPTCHA v3 token injection and form handling
        if (typeof grecaptcha !== 'undefined' && window.RECAPTCHA_SITE_KEY) {

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
            $(document).on('focusin', 'form[hx-post*="process-form"]', function() {
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
            $(document).on('submit', PLAIN_FORM_SELECTOR, function(event) {
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
                        // Native submit() doesn't fire the 'submit' event, so it
                        // can't re-enter this delegated handler (unlike jQuery's
                        // .submit(), which would loop since .off() can't remove
                        // a document-level delegated handler from this element).
                        $form[0].submit();
                    }).catch(function(error) {
                        console.error('reCAPTCHA error:', error);
                        // Allow form to submit anyway - server will handle validation
                        $form[0].submit();
                    });
                });
                
                return false;
            });
        }
    });
})(jQuery);