/*  ---------------------------------------------------
  Template Name: DJoz
  Description:  DJoz Music HTML Template
  Author: Colorlib
  Author URI: https://colorlib.com
  Version: 1.0
  Created: Colorlib
---------------------------------------------------------  */

'use strict';

(function ($) {

    /*------------------
        Preloader
    --------------------*/
    $(window).on('load', function () {
        $(".loader").fadeOut();
        $("#preloder").delay(200).fadeOut("slow");
    });

    /*------------------
		Navigation (header chrome - initialized once, never re-run,
		since htmx boost never swaps the header)
	--------------------*/
    $(".mobile-menu").slicknav({
        prependTo: '#mobile-menu-wrap',
        allowParentLinks: true
    });

    /*------------------------------------------------------------
        Content widgets: everything below targets elements that
        live inside <main>, which htmx boost replaces on navigation
        (see js.html). Re-run scoped to the swapped-in content so
        these keep working after a boosted navigation, and scoped
        to `context` so header/footer elements are never touched.
    ------------------------------------------------------------*/
    function initContentWidgets(context) {
        context = context || document;

        /*------------------
            Background Set
        --------------------*/
        $('.set-bg', context).each(function () {
            var bg = $(this).data('setbg');
            $(this).css('background-image', 'url(' + bg + ')');
        });

        /*--------------------------
            Event Slider
        ----------------------------*/
        $(".event__slider", context).owlCarousel({
            loop: true,
            margin: 0,
            items: 3,
            dots: false,
            nav: true,
            navText: ["<i class='fa fa-angle-left' aria-hidden='true'></i>","<i class='fa fa-angle-right' aria-hidden='true'></i>"],
            smartSpeed: 1200,
            autoHeight: false,
            autoplay: true,
            responsive: {
                992: {
                    items: 3,
                },
                768: {
                    items: 2,
                },
                0: {
                    items: 1,
                },
            }
        });
        $(".event__slider .owl-prev", context).attr("aria-label", "Previous");
        $(".event__slider .owl-next", context).attr("aria-label", "Next");

        /*--------------------------
            Videos Slider
        ----------------------------*/
        $(".videos__slider", context).owlCarousel({
            loop: true,
            margin: 0,
            items: 4,
            dots: false,
            nav: true,
            navText: ["<i class='fa fa-angle-left' aria-hidden='true'></i>","<i class='fa fa-angle-right' aria-hidden='true'></i>"],
            smartSpeed: 1200,
            autoHeight: false,
            autoplay: true,
            responsive: {
                992: {
                    items: 4,
                },
                768: {
                    items: 3,
                },
                576: {
                    items: 2,
                },
                0: {
                    items: 1,
                }
            }
        });
        $(".videos__slider .owl-prev", context).attr("aria-label", "Previous");
        $(".videos__slider .owl-next", context).attr("aria-label", "Next");

        /*--------------------------
            Image Carousel Slider
        ----------------------------*/
        $(".images__slider", context).each(function() {
            var $slider = $(this);
            var autoplay = $slider.data('autoplay') === 'true' || $slider.data('autoplay') === true;
            var autoplaySpeed = $slider.data('autoplay-speed') || 3000;
            var showDots = $slider.data('show-dots') === 'true' || $slider.data('show-dots') === true;
            var slidesToShow = parseInt($slider.data('slides-to-show')) || 4;

            var owlConfig = {
                loop: true,
                margin: 10,
                items: slidesToShow,
                dots: showDots,
                dotsEach: false,
                nav: true,
                navText: ["<i class='fa fa-angle-left' aria-hidden='true'></i>","<i class='fa fa-angle-right' aria-hidden='true'></i>"],
                smartSpeed: 1200,
                autoHeight: false,
                autoplay: autoplay,
                autoplayTimeout: autoplaySpeed,
                autoplayHoverPause: true,
                responsive: {
                    992: {
                        items: slidesToShow,
                        dots: showDots
                    },
                    768: {
                        items: Math.min(3, slidesToShow),
                        dots: showDots
                    },
                    576: {
                        items: Math.min(2, slidesToShow),
                        dots: showDots
                    },
                    0: {
                        items: 1,
                        dots: showDots
                    }
                }
            };

            $slider.owlCarousel(owlConfig);
            $slider.find(".owl-prev").attr("aria-label", "Previous");
            $slider.find(".owl-next").attr("aria-label", "Next");
            $slider.find(".owl-dot").each(function(i) {
                $(this).attr("aria-label", "Slide " + (i + 1));
            });
        });

        /*-------------------
            Nice Scroll (jukebox track list)
        --------------------- */
        $(".nice-scroll", context).niceScroll({
            cursorcolor: "#111111",
            cursorwidth: "5px",
            background: "#e1e1e1",
            cursorborder: "",
            autohidemode: false,
            horizrailenabled: false
        });
    }

    initContentWidgets(document);

    // niceScroll injects its own rail/cursor <div>s next to the elements it
    // scrolls. Since htmx only replaces <main>'s innerHTML, those injected
    // nodes are never automatically cleaned up when the old content goes
    // away - destroy them explicitly before the swap, or they linger on
    // the page after navigating away (e.g. leaving the jukebox block).
    document.body.addEventListener('htmx:beforeSwap', function (evt) {
        $(".nice-scroll", evt.detail.target).each(function () {
            var instance = $(this).getNiceScroll();
            if (instance) {
                instance.remove();
            }
        });
    });

    // Re-run content widget init for the freshly-swapped <main> after
    // an htmx-boosted navigation (header/footer are never swapped, so
    // they're intentionally excluded from this by scoping to evt.detail.target).
    document.body.addEventListener('htmx:afterSwap', function (evt) {
        initContentWidgets(evt.detail.target);
    });

    // Header nav "active" highlighting and the hero/normal header style are
    // rendered server-side from request.path / hero_header, but boosted
    // navigations never re-render the header. Recompute both client-side
    // after each boosted swap, reading the new page's state off <main>'s
    // data-hero-header attribute (set in base.html, included in the
    // hx-select="main" fragment).
    document.body.addEventListener('htmx:afterSettle', function () {
        $(".header__menu a, .header__nav-auth-mobile a").each(function () {
            var linkPath = this.pathname;
            $(this).parent().toggleClass("active", linkPath === window.location.pathname);
        });

        var isHeroHeader = $("#page-meta").data("hero-header") === true;
        $("header").toggleClass("header--normal", !isHeroHeader);
    });

    /*------------------
		Image Popup Modal with Carousel Navigation
	--------------------*/
    var currentCarouselImages = [];
    var currentImageIndex = 0;
    
    // Function to load all images from a carousel
    function loadCarouselImages(carouselId) {
        currentCarouselImages = [];
        // Only select original images, not Owl Carousel clones
        $('[data-carousel-id="' + carouselId + '"].image-popup-trigger').each(function() {
            // Skip cloned items created by Owl Carousel
            if ($(this).closest('.owl-item').hasClass('cloned')) {
                return; // continue to next iteration
            }
            currentCarouselImages.push({
                url: $(this).data('image-url'),
                caption: $(this).data('caption') || '',
                hasLink: $(this).data('has-link') === true,
                linkUrl: $(this).data('link-url') || '',
                linkTarget: $(this).data('link-target') || '_self'
            });
        });
    }
    
    // Function to display an image in the modal
    function showModalImage(index) {
        if (currentCarouselImages.length === 0) return;
        
        // Wrap around if necessary
        if (index < 0) index = currentCarouselImages.length - 1;
        if (index >= currentCarouselImages.length) index = 0;
        
        currentImageIndex = index;
        var img = currentCarouselImages[index];
        
        // Set image source
        $('#imageModalImg').attr('src', img.url);
        $('#imageModalImg').attr('alt', img.caption || 'Full size image');
        
        // Show or hide caption
        if (img.caption) {
            $('#imageModalCaption').text(img.caption).show();
        } else {
            $('#imageModalCaption').hide();
        }
        
        // Show or hide link button
        if (img.hasLink && img.linkUrl) {
            $('#imageModalLinkBtn').attr('href', img.linkUrl);
            $('#imageModalLinkBtn').attr('target', img.linkTarget);
            $('#imageModalLink').show();
        } else {
            $('#imageModalLink').hide();
        }
        
        // Update counter
        if (currentCarouselImages.length > 1) {
            $('#imageModalCounter').text((index + 1) + ' / ' + currentCarouselImages.length).show();
            $('#imageModalPrev').css('display', 'flex');
            $('#imageModalNext').css('display', 'flex');
        } else {
            $('#imageModalCounter').hide();
            $('#imageModalPrev').hide();
            $('#imageModalNext').hide();
        }
    }
    
    // Open modal when clicking on an image
    $(document).on('click', '.image-popup-trigger', function(e) {
        e.preventDefault();
        
        var carouselId = $(this).data('carousel-id');
        var imageIndex = $(this).data('image-index');
        
        // Load all images from this carousel
        loadCarouselImages(carouselId);
        
        // Show the clicked image
        showModalImage(imageIndex);
        
        $('#imageModal').modal('show');
    });
    
    // Previous image button - use event delegation
    $(document).on('click', '#imageModalPrev', function(e) {
        e.preventDefault();
        e.stopPropagation();
        showModalImage(currentImageIndex - 1);
    });
    
    // Next image button - use event delegation
    $(document).on('click', '#imageModalNext', function(e) {
        e.preventDefault();
        e.stopPropagation();
        showModalImage(currentImageIndex + 1);
    });
    
    // Keyboard navigation (left/right arrow keys)
    $(document).on('keydown', function(e) {
        if ($('#imageModal').hasClass('show')) {
            if (e.keyCode === 37) { // Left arrow
                e.preventDefault();
                showModalImage(currentImageIndex - 1);
            } else if (e.keyCode === 39) { // Right arrow
                e.preventDefault();
                showModalImage(currentImageIndex + 1);
            }
        }
    });

    // Clear image when modal is closed
    $('#imageModal').on('hidden.bs.modal', function () {
        $('#imageModalImg').attr('src', '');
        $('#imageModalCaption').text('').hide();
        $('#imageModalLink').hide();
        $('#imageModalCounter').hide();
        $('#imageModalPrev').hide();
        $('#imageModalNext').hide();
        currentCarouselImages = [];
        currentImageIndex = 0;
    });

    /*------------------
		Video Popup Modal
	--------------------*/
    $(document).on('click', '.video-popup-trigger', function(e) {
        e.preventDefault();
        
        var videoUrl = $(this).data('video-url');
        var videoFile = $(this).data('video-file');
        var videoType = $(this).data('video-type');
        
        // Check if it's an uploaded video file
        if (videoFile) {
            // Show HTML5 video player, hide iframe
            $('#videoIframeContainer').hide();
            $('#videoPlayerContainer').show();
            
            // Set video source and type
            $('#videoSource').attr('src', videoFile);
            $('#videoSource').attr('type', 'video/' + videoType);
            
            // Load and play the video
            var videoPlayer = document.getElementById('videoPlayer');
            videoPlayer.load();
            videoPlayer.play();
        } else if (videoUrl) {
            // Show iframe, hide HTML5 player
            $('#videoPlayerContainer').hide();
            $('#videoIframeContainer').show();
            
            // Add autoplay parameter to URL
            if (videoUrl.indexOf('?') > -1) {
                videoUrl += '&autoplay=1';
            } else {
                videoUrl += '?autoplay=1';
            }
            $('#videoIframe').attr('src', videoUrl);
        }
        
        $('#videoModal').modal('show');
    });

    // Clear video when modal is closed to stop playback
    $('#videoModal').on('hidden.bs.modal', function () {
        $('#videoIframe').attr('src', '');
        
        // Stop and reset HTML5 video player
        var videoPlayer = document.getElementById('videoPlayer');
        videoPlayer.pause();
        videoPlayer.currentTime = 0;
        $('#videoSource').attr('src', '');
    });


    /*------------------
		Barfiller
	--------------------*/
    $('#bar1').barfiller({
        barColor: "#ffffff",
    });

    $('#bar2').barfiller({
        barColor: "#ffffff",
    });

    $('#bar3').barfiller({
        barColor: "#ffffff",
    });

})(jQuery);