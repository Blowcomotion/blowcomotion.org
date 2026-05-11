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
    $(".videos__slider").each(function() {
        var $carousel = $(this);
        var columns = parseInt($carousel.data('columns')) || 4;
        
        $carousel.owlCarousel({
            loop: true,
            margin: 0,
            items: columns,
            dots: false,
            nav: true,
            navText: ["<i class='fa fa-angle-left'></i>","<i class='fa fa-angle-right'></i>"],
            smartSpeed: 1200,
            autoHeight: false,
            autoplay: true,
            responsive: {
                992: {
                    items: columns,
                },
                768: {
                    items: Math.min(columns, 3),
                },
                576: {
                    items: Math.min(columns, 2),
                },
                0: {
                    items: 1,
                }
            }
        });
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