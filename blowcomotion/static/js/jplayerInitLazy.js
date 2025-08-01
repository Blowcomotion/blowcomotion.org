// Optimized jPlayer Initialization with Lazy Loading

(function($) {
    var initializedPlayers = new Set();
    var currentlyPlaying = null;

    // Initialize lazy loading on page load
    initLazyPlayers();
    
    function initLazyPlayers() {
        // Only set up click handlers, don't initialize jPlayers yet
        $('.lazy-play-btn').on('click', function(e) {
            e.preventDefault();
            var trackId = $(this).data('track-id');
            var player = $('.jplayer[data-track-id="' + trackId + '"]');
            
            // Show loading spinner
            $(this).find('.loading-spinner').show();
            
            // If player is not initialized, initialize it first
            if (!initializedPlayers.has(trackId)) {
                initializePlayer(player, trackId, $(this));
            } else {
                // Player already initialized, just play/pause
                handlePlayPause(player, $(this));
            }
        });

        // Initialize first player only if preload is enabled
        var firstPlayer = $('.lazy-player').first();
        if (firstPlayer.length > 0) {
            var firstTrackId = firstPlayer.data('track-id');
            var shouldPreload = firstPlayer.data('preload-first') === 'true';
            if (shouldPreload) {
                initializePlayer(firstPlayer, firstTrackId, null, true);
            }
        }
    }
    
    function initializePlayer(player, trackId, clickedBtn, isPreload = false) {
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
                    // Auto-play after initialization
                    if (!isPreload) {
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
                // Show loading state
                if (clickedBtn && !isPreload) {
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
            preload: isPreload ? 'metadata' : 'none', // Only preload first track
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
