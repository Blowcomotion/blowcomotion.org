/**
 * Admin Tool Usage Tracker
 *
 * Fires a small, best-effort ping to /admin-tool-usage/ whenever a staff
 * user views an admin page or clicks a button/link in the main content
 * area, so the team can see which admin tools get used. See issue #311.
 *
 * Intentionally defensive: any failure here must never break the admin UI.
 */
(function () {
    try {
        function getCookie(name) {
            var match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
            return match ? decodeURIComponent(match[1]) : null;
        }

        function send(tool, action) {
            try {
                var payload = JSON.stringify({ tool: tool, action: action || '' });
                var csrftoken = getCookie('csrftoken');

                // Plain JSON fetch with keepalive: survives page navigation
                // like sendBeacon would, but (unlike sendBeacon's FormData)
                // doesn't force the CSRF middleware to consume the request
                // body before our view can read it. Pings fire on load and
                // on click (capture phase, before navigation happens), not
                // on unload, so keepalive is enough here.
                fetch('/admin-tool-usage/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrftoken || '',
                    },
                    body: payload,
                    keepalive: true,
                    credentials: 'same-origin',
                });
            } catch (e) {
                // swallow; tracking must never break the admin UI
            }
        }

        function describeTarget(el) {
            if (!el) return '';
            var label = el.id || el.getAttribute('name') || (el.textContent || '').trim();
            return label.slice(0, 100);
        }

        // Only track within the Wagtail admin, never public pages.
        if (window.location.pathname.indexOf('/admin/') !== 0) {
            return;
        }

        // Page view on load.
        send(window.location.pathname);

        // Clicks on buttons/links within the main content area.
        document.addEventListener('click', function (event) {
            try {
                var target = event.target.closest('button, a, input[type="submit"], input[type="button"]');
                if (!target) return;

                var main = document.querySelector('main, #main, .content-wrapper');
                if (main && !main.contains(target)) return;

                send(window.location.pathname, describeTarget(target));
            } catch (e) {
                // swallow
            }
        }, true);
    } catch (e) {
        // swallow; never break the admin UI
    }
})();
