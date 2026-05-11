/**
 * Image Carousel initialization using Slick Carousel
 */
(function($) {
    'use strict';
    
    function initImageCarousels() {
        $('.image-carousel').each(function() {
            const $carousel = $(this);
            
            // Get configuration from data attributes
            const slidesToShow = parseInt($carousel.data('slides-to-show')) || 3;
            const autoplay = $carousel.data('autoplay') === true || $carousel.data('autoplay') === 'true';
            const autoplaySpeed = parseInt($carousel.data('autoplay-speed')) || 3000;
            
            // Initialize Slick carousel
            $carousel.slick({
                slidesToShow: slidesToShow,
                slidesToScroll: 1,
                autoplay: autoplay,
                autoplaySpeed: autoplaySpeed,
                dots: true,
                arrows: true,
                infinite: true,
                responsive: [
                    {
                        breakpoint: 1024,
                        settings: {
                            slidesToShow: Math.min(3, slidesToShow),
                            slidesToScroll: 1
                        }
                    },
                    {
                        breakpoint: 768,
                        settings: {
                            slidesToShow: Math.min(2, slidesToShow),
                            slidesToScroll: 1
                        }
                    },
                    {
                        breakpoint: 480,
                        settings: {
                            slidesToShow: 1,
                            slidesToScroll: 1
                        }
                    }
                ]
            });
        });
    }
    
    // Initialize on document ready
    $(document).ready(function() {
        initImageCarousels();
    });
    
    // Also initialize after dynamic content loads (for Wagtail preview)
    if (window.wagtail) {
        document.addEventListener('wagtail:tab-changed', function() {
            setTimeout(initImageCarousels, 100);
        });
    }
    
})(jQuery);
