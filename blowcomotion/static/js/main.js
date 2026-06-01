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
        Background Set
    --------------------*/
    $('.set-bg').each(function () {
        var bg = $(this).data('setbg');
        $(this).css('background-image', 'url(' + bg + ')');
    });

    /*------------------
		Navigation
	--------------------*/
    $(".mobile-menu").slicknav({
        prependTo: '#mobile-menu-wrap',
        allowParentLinks: true
    });
    
    /*--------------------------
        Event Slider
    ----------------------------*/
    $(".event__slider").owlCarousel({
        loop: true,
        margin: 0,
        items: 3,
        dots: false,
        nav: true,
        navText: ["<i class='fa fa-angle-left'></i>","<i class='fa fa-angle-right'></i>"],
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
    
    /*--------------------------
        Videos Slider
    ----------------------------*/
    $(".videos__slider").owlCarousel({
        loop: true,
        margin: 0,
        items: 4,
        dots: false,
        nav: true,
        navText: ["<i class='fa fa-angle-left'></i>","<i class='fa fa-angle-right'></i>"],
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

    /*--------------------------
        Image Carousel Slider
    ----------------------------*/
    $(".images__slider").each(function() {
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
            navText: ["<i class='fa fa-angle-left'></i>","<i class='fa fa-angle-right'></i>"],
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
    $('.video-popup-trigger').on('click', function(e) {
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

    /*-------------------
		Nice Scroll
	--------------------- */
    $(".nice-scroll").niceScroll({
        cursorcolor: "#111111",
        cursorwidth: "5px",
        background: "#e1e1e1",
        cursorborder: "",
        autohidemode: false,
        horizrailenabled: false
    });

})(jQuery);