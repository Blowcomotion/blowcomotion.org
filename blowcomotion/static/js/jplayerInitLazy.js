// Optimized jPlayer Initialization with Lazy Loading and Metadata Preloading

(function($) {
    var initializedPlayers = new Set();
    var currentlyPlaying = null;

    // Wait for DOM ready and jPlayer to be available
    $(document).ready(function() {
        // Check if jPlayer is available
        if (typeof $.fn.jPlayer === 'undefined') {
            console.error('jPlayer not loaded yet, retrying...');
            setTimeout(function() {
                if (typeof $.fn.jPlayer !== 'undefined') {
                    initLazyPlayers();
                }
            }, 100);
        } else {
            initLazyPlayers();
        }
    });
    
    function initLazyPlayers() {
        // Initialize all players with metadata preloading only
        $('.lazy-player').each(function() {
            var player = $(this);
            var trackId = player.data('track-id');
            
            // Initialize with metadata preloading for duration info
            initializePlayer(player, trackId, null, true);
        });
        
        // Set up click handlers for actual playback
        $('.lazy-play-btn').on('click', function(e) {
            e.preventDefault();
            var trackId = $(this).data('track-id');
            var player = $('.jplayer[data-track-id="' + trackId + '"]');
            
            // Show loading spinner
            $(this).find('.loading-spinner').show();
            
            // If player is not initialized, initialize it first
            if (!initializedPlayers.has(trackId)) {
                initializePlayer(player, trackId, $(this), false);
            } else {
                // Player already initialized, just play/pause
                handlePlayPause(player, $(this));
            }
        });
    }
    
    function initializePlayer(player, trackId, clickedBtn, isMetadataOnly) {
        var ancestor = player.data('ancestor');
        var songUrl = player.data('url');
        
        player.jPlayer({
            ready: function () {
                $(this).jPlayer("setMedia", {
                    mp3: songUrl
                });
                
                // Mark as initialized
                initializedPlayers.add(trackId);
                player.data('initialized', 'true');
                
                // Hide loading spinner if this was triggered by a click
                if (clickedBtn) {
                    clickedBtn.find('.loading-spinner').hide();
                    // Auto-play after initialization if not metadata-only
                    if (!isMetadataOnly) {
                        $(this).jPlayer("play");
                        currentlyPlaying = trackId;
                    }
                }
            },
            play: function() {
                // Pause other players
                $(this).jPlayer("pauseOthers");
                currentlyPlaying = trackId;
                
                // Update UI
                $('.jp-play').removeClass('jp-pause');
                $(ancestor + ' .jp-play').addClass('jp-pause');
                
                try {
                    if (typeof wavesurfer !== 'undefined') {
                        wavesurfer.pause();
                    }
                } catch(err) {
                    // Ignore wavesurfer errors
                }
            },
            pause: function() {
                $(ancestor + ' .jp-play').removeClass('jp-pause');
                if (currentlyPlaying === trackId) {
                    currentlyPlaying = null;
                }
            },
            ended: function() {
                $(ancestor + ' .jp-play').removeClass('jp-pause');
                currentlyPlaying = null;
            },
            loadstart: function() {
                // Show loading state for actual playback, not metadata
                if (clickedBtn && !isMetadataOnly) {
                    clickedBtn.find('.loading-spinner').show();
                }
            },
            canplay: function() {
                // Hide loading state
                if (clickedBtn) {
                    clickedBtn.find('.loading-spinner').hide();
                }
            },
            error: function(event) {
                console.error('jPlayer error for track ' + trackId + ':', event.jPlayer.error);
                if (clickedBtn) {
                    clickedBtn.find('.loading-spinner').hide();
                }
            },
            swfPath: "jPlayer",
            supplied: "mp3",
            cssSelectorAncestor: ancestor,
            wmode: "window",
            globalVolume: false,
            useStateClassSkin: true,
            autoBlur: false,
            smoothPlayBar: true,
            keyEnabled: true,
            solution: 'html',
            preload: 'metadata', // Always load metadata for duration
            volume: 0.8,
            muted: false,
            backgroundColor: '#000000',
            errorAlerts: false,
            warningAlerts: false
        });
    }
    
    function handlePlayPause(player, clickedBtn) {
        var trackId = player.data('track-id');
        
        // Hide loading spinner
        clickedBtn.find('.loading-spinner').hide();
        
        // Check current state and toggle
        if (currentlyPlaying === trackId) {
            player.jPlayer("pause");
        } else {
            player.jPlayer("play");
        }
    }

    // Current time alignment function (from original)
    function currentTimeAlign() {
        $('.jp-progress').each(function() {
            var jpPBarW = $(this).find('.jp-play-bar').innerWidth();
            if(jpPBarW > 40) {
                $(this).addClass('middle');
            } else {
                $(this).removeClass('middle');
            }
        });
    }
    setInterval(currentTimeAlign, 10);

    // Fast forward and rewind functionality (from original)
    $('.single_player_container').each(function() {
        var rwaction,
            rewinding,
            fastforward,
            thisItem = $(this);

        thisItem.find('.jp-next').click(function (e) { 
            var trackId = thisItem.data('track-id');
            var player = thisItem.find('.jplayer');
            if (initializedPlayers.has(trackId)) {
                FastforwardTrack(player, thisItem);
            }
        });

        thisItem.find('.jp-prev').click(function (e) { 
            var trackId = thisItem.data('track-id');
            var player = thisItem.find('.jplayer');
            if (initializedPlayers.has(trackId)) {
                RewindTrack(player, thisItem);
            }
        });

        function GetPlayerProgress() {
            return (thisItem.find('.jp-play-bar').width() / thisItem.find('.jp-seek-bar').width() * 100);
        }

        function RewindTrack(player, item) {
            var currentProgress = GetPlayerProgress();
            var futureProgress = currentProgress - 5;
            if (futureProgress <= 0) {
                rewinding = false;
                window.clearInterval(rwaction);
                player.jPlayer("pause", 0);
            } else {
                player.jPlayer("playHead", parseInt(futureProgress, 10));
            }
        }

        function FastforwardTrack(player, item) {
            var currentProgress = GetPlayerProgress();
            var futureProgress = currentProgress + 5;
            if (futureProgress >= 100) {
                fastforward = false;
                window.clearInterval(rwaction);
                player.jPlayer("playHead", parseInt(item.find('.jp-duration').text().replace(':', '')));
            } else {
                player.jPlayer("playHead", parseInt(futureProgress, 10));
            }
        }
    });

})(jQuery);
