/**
 * Video Title Resolver Controller
 * Fetches video titles from URLs and updates the minimap display
 */
class VideoTitleResolverController extends window.StimulusModule.Controller {
    connect() {
        // Observe the entire document for new video inputs
        this.setupInputObserver();
        // Process any existing inputs
        this.observeVideoInputs();
    }

    setupInputObserver() {
        // Watch for new StreamField blocks being added
        this.observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) { // Element node
                        // Check if the added node or its descendants contain video inputs
                        const inputs = node.querySelectorAll ? node.querySelectorAll('input[name*="-video"]') : [];
                        inputs.forEach(input => {
                            if (this.isVideoUrlInput(input) && !input.dataset.videoTitleResolverAttached) {
                                this.attachListeners(input);
                            }
                        });
                    }
                });
            });
        });

        this.observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    observeVideoInputs() {
        // Target all EmbedBlock inputs within VideoItemBlock
        const videoInputs = document.querySelectorAll('input[name*="-video"]');
        
        videoInputs.forEach(input => {
            if (this.isVideoUrlInput(input) && !input.dataset.videoTitleResolverAttached) {
                this.attachListeners(input);
            }
        });
    }

    attachListeners(input) {
        // Mark as attached to avoid duplicate listeners
        input.dataset.videoTitleResolverAttached = 'true';
        
        // Listen for changes and blur events
        input.addEventListener('change', (e) => this.handleUrlChange(e));
        input.addEventListener('blur', (e) => this.handleUrlChange(e));
        
        // If there's already a value, fetch the title
        if (input.value) {
            this.fetchAndUpdateTitle(input);
        }
    }

    isVideoUrlInput(input) {
        const name = input.getAttribute('name');
        // Match pattern ending with -value-videos-N-value-video
        // This works for nested StreamFields (e.g., column_layout) too
        return name && /-value-videos-\d+-value-video$/.test(name);
    }

    handleUrlChange(event) {
        const input = event.target;
        const url = input.value.trim();
        
        if (url && this.isValidVideoUrl(url)) {
            this.fetchAndUpdateTitle(input);
        }
    }

    isValidVideoUrl(url) {
        // Check if it's a YouTube or Vimeo URL
        return /youtube\.com\/watch|youtu\.be\/|vimeo\.com\//i.test(url);
    }

    async fetchAndUpdateTitle(input) {
        const url = input.value.trim();
        if (!url) return;

        try {
            // Derive admin URL from current location to handle custom admin paths
            const adminBase = this.getAdminBase();
            const response = await fetch(`${adminBase}/embeds/fetch/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': this.getCsrfToken(),
                },
                body: `url=${encodeURIComponent(url)}`
            });

            if (response.ok) {
                const data = await response.json();
                if (data.title) {
                    // Wait for minimap to be available, then update
                    this.waitForMinimapAndUpdate(input, data.title);
                }
            }
        } catch (error) {
            console.warn('Failed to fetch video title:', error);
        }
    }

    waitForMinimapAndUpdate(input, title, attempts = 0) {
        const maxAttempts = 20; // Try for up to 2 seconds
        
        // Check if minimap exists
        const minimapExists = document.querySelector('.w-minimap__list');
        
        if (minimapExists) {
            this.updateMinimapLabel(input, title);
        } else if (attempts < maxAttempts) {
            // Minimap not ready yet, try again after 100ms
            setTimeout(() => {
                this.waitForMinimapAndUpdate(input, title, attempts + 1);
            }, 100);
        }
    }

    updateMinimapLabel(input, title) {
        // Find the parent block that contains this input
        // StreamField blocks have IDs like: block-{uuid}-content
        let parentBlock = input.closest('[id^="block-"]');
        
        if (!parentBlock) {
            return;
        }
        
        let blockId = parentBlock.id;
        
        // The minimap uses -section suffix, but the block has -content suffix
        // Remove -content and add -section
        if (blockId.endsWith('-content')) {
            blockId = blockId.replace('-content', '');
        }
        
        // Find the corresponding minimap link (pattern: #block-{uuid}-section)
        // Specifically target minimap items, not panel anchors
        const minimapLink = document.querySelector(`a.w-minimap-item[href="#${blockId}-section"]`);
        
        if (!minimapLink) {
            return;
        }
        
        const labelElement = minimapLink.querySelector('.w-minimap-item__text');
        if (labelElement) {
            // Update the text content, truncate if too long
            const truncatedTitle = title.length > 30 ? title.substring(0, 27) + '…' : title;
            labelElement.textContent = truncatedTitle;
            
            // Store full title as tooltip
            minimapLink.setAttribute('title', title);
        }
    }

    getAdminBase() {
        // Extract admin base from current URL (works for default /admin/ or custom paths)
        const match = window.location.pathname.match(/^(\/.*?\/admin)/);
        return match ? match[1] : '/admin';
    }

    getCsrfToken() {
        // Get CSRF token from cookie or from a hidden input
        const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (tokenInput) {
            return tokenInput.value;
        }
        
        // Fallback: get from cookie
        const name = 'csrftoken';
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const trimmed = cookie.trim();
            if (trimmed.startsWith(name + '=')) {
                return trimmed.substring(name.length + 1);
            }
        }
        return '';
    }

    disconnect() {
        // Clean up observer when controller is disconnected
        if (this.observer) {
            this.observer.disconnect();
        }
    }
}

// Register the controller with a data-controller attribute on body or main container
window.wagtail.app.register('video-title-resolver', VideoTitleResolverController);

// Auto-initialize on document load
document.addEventListener('DOMContentLoaded', () => {
    // Add the controller to the main content area if not already present
    const mainContent = document.querySelector('[data-edit-form], main, body');
    if (mainContent && !mainContent.hasAttribute('data-controller')) {
        mainContent.setAttribute('data-controller', 'video-title-resolver');
    } else if (mainContent && mainContent.hasAttribute('data-controller')) {
        const controllers = mainContent.getAttribute('data-controller');
        if (!controllers.includes('video-title-resolver')) {
            mainContent.setAttribute('data-controller', controllers + ' video-title-resolver');
        }
    }
});

