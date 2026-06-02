/**
 * Chart Library Block JavaScript
 * 
 * Nested accordion structure: Section → Instrument → Song → Part
 * Features:
 * - Lazy loading of songs when instrument expands
 * - Inline audio player below song row
 * - Per-section search filtering
 * - Multiple sections can be open simultaneously
 */

(function() {
    'use strict';

    // Debounce utility
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // Global click handler for closing dropdowns (registered once)
    let globalClickHandlerRegistered = false;
    function registerGlobalClickHandler() {
        if (globalClickHandlerRegistered) return;
        globalClickHandlerRegistered = true;
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.video-dropdown')) {
                document.querySelectorAll('.chart-accordion .video-dropdown.open').forEach(d => {
                    d.classList.remove('open');
                });
            }
        });
    }

    // Initialize all chart library blocks on the page
    function initChartLibraryBlocks() {
        const blocks = document.querySelectorAll('.chart-library-block');
        blocks.forEach(block => new ChartLibrary(block));
    }

    class ChartLibrary {
        constructor(container) {
            this.container = container;
            this.accordion = container.querySelector('.chart-accordion');
            this.showSearch = this.accordion.dataset.showSearch === 'true';
            this.searchPlaceholder = this.accordion.dataset.searchPlaceholder || 'Search for a song...';
            
            this.state = {
                currentlyPlayingUrl: null,
                currentAudioPlayer: null,
                loadedInstruments: new Set() // Track which instruments have loaded songs
            };

            this.init();
        }

        init() {
            this.bindEvents();
            this.loadSections();
        }

        bindEvents() {
            // Click delegation for accordion
            this.accordion.addEventListener('click', (e) => {
                // Section header toggle
                const sectionHeader = e.target.closest('.accordion-section-header');
                if (sectionHeader) {
                    this.toggleSection(sectionHeader.closest('.accordion-section'));
                    return;
                }

                // Instrument header toggle
                const instrumentHeader = e.target.closest('.accordion-instrument-header');
                if (instrumentHeader) {
                    this.toggleInstrument(instrumentHeader.closest('.accordion-instrument'));
                    return;
                }

                // Song header toggle (for parts expansion)
                const songHeader = e.target.closest('.accordion-song-header');
                if (songHeader && !e.target.closest('.song-play-btn') && !e.target.closest('.chart-pdf-btn') && !e.target.closest('.song-video-btn') && !e.target.closest('.video-dropdown')) {
                    const songItem = songHeader.closest('.accordion-song');
                    if (songItem.dataset.hasMultiple === 'true') {
                        this.toggleSongParts(songItem);
                    }
                    return;
                }

                // Play button click
                const playBtn = e.target.closest('.song-play-btn');
                if (playBtn) {
                    e.stopPropagation();
                    const songItem = playBtn.closest('.accordion-song');
                    if (songItem) {
                        this.playSong(songItem);
                    }
                    return;
                }

                // Video dropdown toggle
                const dropdownToggle = e.target.closest('.video-dropdown-toggle');
                if (dropdownToggle) {
                    e.stopPropagation();
                    const dropdown = dropdownToggle.closest('.video-dropdown');
                    this.accordion.querySelectorAll('.video-dropdown.open').forEach(d => {
                        if (d !== dropdown) d.classList.remove('open');
                    });
                    dropdown.classList.toggle('open');
                    return;
                }
            });

            // Register global click handler for closing dropdowns (once for all instances)
            registerGlobalClickHandler();

            // Keyboard support for accordion headers
            this.accordion.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    const sectionHeader = e.target.closest('.accordion-section-header');
                    if (sectionHeader) {
                        e.preventDefault();
                        this.toggleSection(sectionHeader.closest('.accordion-section'));
                        return;
                    }

                    const instrumentHeader = e.target.closest('.accordion-instrument-header');
                    if (instrumentHeader) {
                        e.preventDefault();
                        this.toggleInstrument(instrumentHeader.closest('.accordion-instrument'));
                        return;
                    }

                    const songHeader = e.target.closest('.accordion-song-header[role="button"]');
                    if (songHeader) {
                        e.preventDefault();
                        this.toggleSongParts(songHeader.closest('.accordion-song'));
                        return;
                    }
                }
            });
        }

        async loadSections() {
            try {
                const response = await fetch('/charts/instruments/');
                const data = await response.json();
                this.renderSections(data.sections);
            } catch (error) {
                console.error('Error loading sections:', error);
                this.accordion.innerHTML = '<div class="accordion-error">Error loading chart library</div>';
            }
        }

        renderSections(sections) {
            if (sections.length === 0) {
                this.accordion.innerHTML = '<div class="accordion-empty">No charts available</div>';
                return;
            }

            const html = sections.map(section => `
                <div class="accordion-section" data-section-id="${section.id}">
                    <div class="accordion-section-header" role="button" tabindex="0" aria-expanded="false">
                        <i class="fa fa-chevron-right accordion-icon"></i>
                        <span class="accordion-section-title">${this.escapeHtml(section.name)}</span>
                        <span class="accordion-count">${section.instruments.length} instrument${section.instruments.length !== 1 ? 's' : ''}</span>
                    </div>
                    <div class="accordion-section-content">
                        <div class="accordion-instruments">
                            ${section.instruments.map(instrument => `
                                <div class="accordion-instrument" 
                                     data-instrument-id="${instrument.id}"
                                     data-instrument-name="${this.escapeHtml(instrument.name)}">
                                    <div class="accordion-instrument-header" role="button" tabindex="0" aria-expanded="false">
                                        <i class="fa fa-chevron-right accordion-icon"></i>
                                        <span class="accordion-instrument-title">${this.escapeHtml(instrument.name)}</span>
                                    </div>
                                    <div class="accordion-instrument-content">
                                        ${this.showSearch ? `
                                        <div class="instrument-search-container">
                                            <input type="text" 
                                                   class="form-control instrument-search-input" 
                                                   placeholder="${this.escapeHtml(this.searchPlaceholder)}"
                                                   data-instrument-id="${instrument.id}"
                                                   aria-label="Search songs for ${this.escapeHtml(instrument.name)}">
                                        </div>
                                        ` : ''}
                                        <div class="accordion-songs">
                                            <div class="accordion-loading">
                                                <span class="spinner-border spinner-border-sm" role="status"></span>
                                                Loading songs...
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            `).join('');

            this.accordion.innerHTML = html;
            
            // Bind search inputs
            if (this.showSearch) {
                this.accordion.querySelectorAll('.instrument-search-input').forEach(input => {
                    const debouncedSearch = debounce((query, instrumentId) => {
                        this.filterSongsInInstrument(instrumentId, query);
                    }, 300);
                    
                    input.addEventListener('input', (e) => {
                        debouncedSearch(e.target.value, e.target.dataset.instrumentId);
                    });
                });
            }
        }

        toggleSection(section) {
            const isExpanded = section.classList.toggle('expanded');
            const header = section.querySelector('.accordion-section-header');
            if (header) header.setAttribute('aria-expanded', isExpanded);
            
            // Pause and cleanup audio player if collapsing and it's inside this section
            if (!isExpanded && this.state.currentAudioPlayer && section.contains(this.state.currentAudioPlayer)) {
                const audioEl = this.state.currentAudioPlayer.querySelector('audio');
                if (audioEl) audioEl.pause();
                const oldPlayBtn = this.state.currentAudioPlayer.closest('.accordion-song')?.querySelector('.song-play-btn');
                if (oldPlayBtn) {
                    oldPlayBtn.classList.remove('playing');
                    oldPlayBtn.querySelector('i').className = 'fa fa-play-circle';
                }
                this.state.currentAudioPlayer.remove();
                this.state.currentAudioPlayer = null;
                this.state.currentlyPlayingUrl = null;
            }
        }

        async toggleInstrument(instrument) {
            const isExpanded = instrument.classList.contains('expanded');
            
            const header = instrument.querySelector('.accordion-instrument-header');
            
            if (isExpanded) {
                instrument.classList.remove('expanded');
                if (header) header.setAttribute('aria-expanded', 'false');
                // Pause and cleanup audio player if it's inside this instrument
                if (this.state.currentAudioPlayer && instrument.contains(this.state.currentAudioPlayer)) {
                    const audioEl = this.state.currentAudioPlayer.querySelector('audio');
                    if (audioEl) audioEl.pause();
                    const oldPlayBtn = this.state.currentAudioPlayer.closest('.accordion-song')?.querySelector('.song-play-btn');
                    if (oldPlayBtn) {
                        oldPlayBtn.classList.remove('playing');
                        oldPlayBtn.querySelector('i').className = 'fa fa-play-circle';
                    }
                    this.state.currentAudioPlayer.remove();
                    this.state.currentAudioPlayer = null;
                    this.state.currentlyPlayingUrl = null;
                }
            } else {
                instrument.classList.add('expanded');
                if (header) header.setAttribute('aria-expanded', 'true');
                
                // Lazy load songs if not already loaded
                const instrumentId = instrument.dataset.instrumentId;
                if (!this.state.loadedInstruments.has(instrumentId)) {
                    const loaded = await this.loadSongsForInstrument(instrument);
                    if (loaded) this.state.loadedInstruments.add(instrumentId);
                }
            }
        }

        async loadSongsForInstrument(instrumentElement, searchQuery = '') {
            const instrumentId = instrumentElement.dataset.instrumentId;
            const songsContainer = instrumentElement.querySelector('.accordion-songs');
            
            try {
                const url = searchQuery 
                    ? `/charts/songs/${instrumentId}/?search=${encodeURIComponent(searchQuery)}`
                    : `/charts/songs/${instrumentId}/`;
                
                const response = await fetch(url);
                const data = await response.json();
                
                this.renderSongs(songsContainer, data.songs, instrumentId);
                return true;
            } catch (error) {
                console.error('Error loading songs:', error);
                songsContainer.innerHTML = '<div class="accordion-error">Error loading songs</div>';
                return false;
            }
        }

        renderSongs(container, songs, instrumentId) {
            if (songs.length === 0) {
                container.innerHTML = '<div class="accordion-empty">No songs found</div>';
                return;
            }

            const html = songs.map(song => {
                const hasMultipleCharts = song.charts && song.charts.length > 1;
                const hasSingleChart = song.charts && song.charts.length === 1;
                const pdfUrl = hasSingleChart ? song.charts[0].pdf_url : '';
                
                return `
                <div class="accordion-song" 
                     data-song-id="${song.id}"
                     data-song-title="${this.escapeHtml(song.title)}"
                     data-has-recording="${song.has_recording}"
                     data-recording-url="${this.escapeHtml(song.recording_url || '')}"
                     data-has-video="${song.has_video}"
                     data-videos='${JSON.stringify(song.videos || []).replace(/'/g, "&#39;")}'
                     data-has-multiple="${hasMultipleCharts}"
                     data-charts='${JSON.stringify(song.charts || []).replace(/'/g, "&#39;")}'
                     data-instrument-id="${instrumentId}">
                    <div class="accordion-song-header"${hasMultipleCharts ? ' role="button" tabindex="0" aria-expanded="false"' : ''}>
                        <span class="song-media-icons">
                            <span class="media-icon-slot">
                                ${song.has_recording ? `
                                    <button type="button" class="song-play-btn" title="Play recording" aria-label="Play ${this.escapeHtml(song.title)}">
                                        <i class="fa fa-play-circle"></i>
                                    </button>
                                ` : ''}
                            </span>
                            <span class="media-icon-slot">
                                ${this.renderVideoButtons(song)}
                            </span>
                        </span>
                        <span class="accordion-song-title">${this.escapeHtml(song.title)}</span>
                        <span class="song-actions">
                            ${hasMultipleCharts ? '<i class="fa fa-chevron-right accordion-icon song-expand-icon"></i>' : ''}
                            ${pdfUrl ? `
                                <a href="${this.escapeHtml(pdfUrl)}" class="btn btn-sm btn-primary chart-pdf-btn" target="_blank" rel="noopener" title="Open Chart PDF">
                                    <i class="fa fa-file-pdf-o"></i>
                                    PDF
                                </a>
                            ` : ''}
                        </span>
                    </div>
                    <div class="accordion-song-content">
                        <!-- Parts will be rendered here when expanded -->
                    </div>
                </div>
            `;
            }).join('');

            container.innerHTML = html;

            // Re-apply search filter if there's an active search query
            const instrumentEl = container.closest('.accordion-instrument');
            const searchInput = instrumentEl ? instrumentEl.querySelector('.instrument-search-input') : null;
            if (searchInput && searchInput.value.trim()) {
                this.filterSongsInInstrument(instrumentId, searchInput.value);
            }
        }

        renderVideoButtons(song) {
            if (!song.has_video || !song.videos || song.videos.length === 0) {
                return '';
            }
            
            if (song.videos.length === 1) {
                return `
                    <a href="${this.escapeHtml(song.videos[0].url)}" class="song-video-btn" target="_blank" rel="noopener" title="${this.escapeHtml(song.videos[0].title || 'Watch video')}" aria-label="Watch video for ${this.escapeHtml(song.title)}">
                        <i class="fa fa-youtube-play"></i>
                    </a>
                `;
            }

            return `
                <div class="video-dropdown">
                    <button type="button" class="song-video-btn video-dropdown-toggle" title="Watch videos" aria-label="Watch videos for ${this.escapeHtml(song.title)}">
                        <i class="fa fa-youtube-play"></i>
                        <span class="video-count">${song.videos.length}</span>
                    </button>
                    <div class="video-dropdown-menu">
                        ${song.videos.map((v, i) => `
                            <a href="${this.escapeHtml(v.url)}" class="video-dropdown-item" target="_blank" rel="noopener">
                                <i class="fa fa-play"></i> ${this.escapeHtml(v.title || 'Video ' + (i + 1))}
                            </a>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        toggleSongParts(songItem) {
            const isExpanded = songItem.classList.contains('expanded');
            const content = songItem.querySelector('.accordion-song-content');
            const expandIcon = songItem.querySelector('.song-expand-icon');
            const header = songItem.querySelector('.accordion-song-header');
            
            if (isExpanded) {
                songItem.classList.remove('expanded');
                if (expandIcon) expandIcon.className = 'fa fa-chevron-right accordion-icon song-expand-icon';
                if (header) header.setAttribute('aria-expanded', 'false');
                content.innerHTML = '';
            } else {
                songItem.classList.add('expanded');
                if (expandIcon) expandIcon.className = 'fa fa-chevron-down accordion-icon song-expand-icon';
                if (header) header.setAttribute('aria-expanded', 'true');
                
                // Render parts
                try {
                    const charts = JSON.parse(songItem.dataset.charts || '[]');
                    if (charts.length > 0) {
                        const partsHtml = charts.map(chart => `
                            <div class="accordion-part" data-chart-id="${chart.id}">
                                <span class="part-name">${this.escapeHtml(chart.part)}</span>
                                ${chart.pdf_url ? `
                                    <a href="${this.escapeHtml(chart.pdf_url)}" class="btn btn-sm btn-primary chart-pdf-btn" target="_blank" rel="noopener" title="Open Chart PDF">
                                        <i class="fa fa-file-pdf-o"></i>
                                        PDF
                                    </a>
                                ` : ''}
                            </div>
                        `).join('');
                        content.innerHTML = `<div class="accordion-parts">${partsHtml}</div>`;
                    }
                } catch (error) {
                    console.error('Error parsing charts:', error);
                }
            }
        }

        playSong(songItem) {
            const recordingUrl = songItem.dataset.recordingUrl;
            const songTitle = songItem.dataset.songTitle;

            if (!recordingUrl) return;

            const playBtn = songItem.querySelector('.song-play-btn');
            
            // If clicking the same song that's playing, toggle play/pause
            if (this.state.currentlyPlayingUrl === recordingUrl && this.state.currentAudioPlayer) {
                const audioEl = this.state.currentAudioPlayer.querySelector('audio');
                if (audioEl.paused) {
                    audioEl.play().catch(err => {
                        console.error('Error playing audio:', err);
                    });
                } else {
                    audioEl.pause();
                }
                return;
            }

            // Remove any existing audio player
            if (this.state.currentAudioPlayer) {
                const oldAudioEl = this.state.currentAudioPlayer.querySelector('audio');
                if (oldAudioEl) oldAudioEl.pause();

                const oldPlayBtn = this.accordion.querySelector('.song-play-btn.playing');
                if (oldPlayBtn) {
                    oldPlayBtn.classList.remove('playing');
                    const icon = oldPlayBtn.querySelector('i');
                    if (icon) icon.className = 'fa fa-play-circle';
                }
                this.state.currentAudioPlayer.remove();
                this.state.currentAudioPlayer = null;
                this.state.currentlyPlayingUrl = null;
            }

            // Create inline audio player
            let videos = [];
            try {
                videos = JSON.parse(songItem.dataset.videos || '[]');
            } catch (e) {
                console.error('Error parsing videos data:', e);
            }
            const videoLinksHtml = videos.length > 0 ? `
                <span class="audio-video-links">
                    ${videos.map((v, i) => `
                        <a href="${this.escapeHtml(v.url)}" class="video-link" target="_blank" rel="noopener" title="${this.escapeHtml(v.title || 'Video ' + (i + 1))}">
                            <i class="fa fa-youtube-play"></i>${videos.length > 1 ? ' ' + this.escapeHtml(v.title || 'Video ' + (i + 1)) : ''}
                        </a>
                    `).join('')}
                </span>
            ` : '';

            const playerHtml = `
                <div class="inline-audio-player">
                    <div class="audio-player-header">
                        <span class="now-playing-label">Now Playing:</span>
                        <span class="now-playing-title">${this.escapeHtml(songTitle)}</span>
                        ${videoLinksHtml}
                    </div>
                    <audio controls class="audio-element w-100">
                        <source src="${this.escapeHtml(recordingUrl)}" type="audio/mpeg">
                        Your browser does not support the audio element.
                    </audio>
                </div>
            `;

            // Insert player after song header
            const songHeader = songItem.querySelector('.accordion-song-header');
            songHeader.insertAdjacentHTML('afterend', playerHtml);

            const player = songItem.querySelector('.inline-audio-player');
            const audioEl = player.querySelector('audio');
            
            this.state.currentlyPlayingUrl = recordingUrl;
            this.state.currentAudioPlayer = player;

            // Handle audio events - let events drive button state
            audioEl.addEventListener('ended', () => {
                playBtn.classList.remove('playing');
                playBtn.querySelector('i').className = 'fa fa-play-circle';
            });

            audioEl.addEventListener('pause', () => {
                playBtn.classList.remove('playing');
                playBtn.querySelector('i').className = 'fa fa-play-circle';
            });

            audioEl.addEventListener('play', () => {
                playBtn.classList.add('playing');
                playBtn.querySelector('i').className = 'fa fa-pause-circle';
            });

            // Explicitly start playback (autoplay may be blocked)
            audioEl.play().catch(err => {
                console.error('Error playing audio:', err);
            });
        }

        filterSongsInInstrument(instrumentId, query) {
            const instrument = this.accordion.querySelector(`.accordion-instrument[data-instrument-id="${instrumentId}"]`);
            if (!instrument) return;

            const songs = instrument.querySelectorAll('.accordion-song');
            const lowerQuery = query.toLowerCase().trim();

            songs.forEach(song => {
                const title = (song.dataset.songTitle || '').toLowerCase();
                const isPlayingSong = this.state.currentAudioPlayer && song.contains(this.state.currentAudioPlayer);
                const matches = isPlayingSong || !lowerQuery || title.includes(lowerQuery);
                song.style.display = matches ? '' : 'none';
            });
        }

        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initChartLibraryBlocks);
    } else {
        initChartLibraryBlocks();
    }
})();
