/**
 * Chart Library Block JavaScript
 * 
 * Handles:
 * - Instrument-first selection flow (instrument → song → part)
 * - Song search with debounce
 * - HTML5 audio playback for song recordings
 * - Dynamic chart PDF link display
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

    // Initialize all chart library blocks on the page
    function initChartLibraryBlocks() {
        const blocks = document.querySelectorAll('.chart-library-block');
        blocks.forEach(block => new ChartLibrary(block));
    }

    class ChartLibrary {
        constructor(container) {
            this.container = container;
            this.state = {
                selectedInstrument: null,
                currentlyPlayingUrl: null
            };

            // Cache DOM elements  
            this.elements = {
                searchInput: container.querySelector('.chart-search-input'),
                searchContainer: container.querySelector('.chart-search-container'),
                instrumentList: container.querySelector('.instrument-list'),
                songSection: container.querySelector('.song-section'),
                songList: container.querySelector('.song-list'),
                audioPlayer: container.querySelector('.chart-audio-player'),
                audioElement: container.querySelector('.chart-audio-element'),
                nowPlayingTitle: container.querySelector('.now-playing-title')
            };

            this.init();
        }

        init() {
            this.bindEvents();
            this.loadInstruments();
        }

        bindEvents() {
            // Search input with debounce (filters songs for selected instrument)
            if (this.elements.searchInput) {
                const debouncedSearch = debounce((query) => {
                    if (this.state.selectedInstrument) {
                        this.loadSongsForInstrument(this.state.selectedInstrument.id, query);
                    }
                }, 300);

                this.elements.searchInput.addEventListener('input', (e) => {
                    debouncedSearch(e.target.value);
                });
            }

            // Instrument list click delegation
            this.elements.instrumentList.addEventListener('click', (e) => {
                // Handle section header toggle
                const sectionHeader = e.target.closest('.section-header');
                if (sectionHeader) {
                    this.toggleSection(sectionHeader);
                    return;
                }
                
                const instrumentItem = e.target.closest('.selector-item');
                if (instrumentItem) {
                    this.selectInstrument(instrumentItem);
                }
            });

            // Song list click delegation
            this.elements.songList.addEventListener('click', (e) => {
                // Handle video dropdown toggle
                const dropdownToggle = e.target.closest('.video-dropdown-toggle');
                if (dropdownToggle) {
                    e.stopPropagation();
                    const dropdown = dropdownToggle.closest('.video-dropdown');
                    // Close other dropdowns
                    this.elements.songList.querySelectorAll('.video-dropdown.open').forEach(d => {
                        if (d !== dropdown) d.classList.remove('open');
                    });
                    dropdown.classList.toggle('open');
                    return;
                }
                
                // Handle play button click
                const playBtn = e.target.closest('.song-play-btn:not(.video-dropdown-toggle)');
                if (playBtn) {
                    e.stopPropagation();
                    const songItem = playBtn.closest('.selector-item');
                    if (songItem) {
                        this.playSong(songItem);
                    }
                    return;
                }

                // Handle expand/collapse for songs with multiple parts
                const songItem = e.target.closest('.selector-item:not(.part-item)');
                if (songItem && !e.target.closest('.chart-pdf-btn')) {
                    this.toggleSongParts(songItem);
                }
            });

            // Close dropdowns when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.video-dropdown')) {
                    this.elements.songList.querySelectorAll('.video-dropdown.open').forEach(d => {
                        d.classList.remove('open');
                    });
                }
            });
        }

        async loadInstruments() {
            this.showLoading(this.elements.instrumentList);
            
            try {
                const response = await fetch('/charts/instruments/');
                const data = await response.json();
                
                this.renderInstrumentList(data.sections);
            } catch (error) {
                console.error('Error loading instruments:', error);
                this.elements.instrumentList.innerHTML = '<div class="selector-error">Error loading instruments</div>';
            }
        }

        renderInstrumentList(sections) {
            if (sections.length === 0) {
                this.elements.instrumentList.innerHTML = '<div class="selector-empty">No instruments found</div>';
                return;
            }

            const html = sections.map(section => `
                <div class="section-group collapsed">
                    <div class="section-header">
                        <i class="fa fa-chevron-down section-expand-icon"></i>
                        ${this.escapeHtml(section.name)}
                    </div>
                    <div class="section-instruments">
                    ${section.instruments.map(instrument => `
                        <div class="selector-item instrument-item"
                             role="option"
                             data-instrument-id="${instrument.id}"
                             data-instrument-name="${this.escapeHtml(instrument.name)}">
                            <span class="selector-item-text">${this.escapeHtml(instrument.name)}</span>
                        </div>
                    `).join('')}
                    </div>
                </div>
            `).join('');

            this.elements.instrumentList.innerHTML = html;
        }

        async selectInstrument(instrumentItem) {
            // Update UI state
            this.elements.instrumentList.querySelectorAll('.selector-item').forEach(item => {
                item.classList.remove('active');
                item.setAttribute('aria-selected', 'false');
            });
            instrumentItem.classList.add('active');
            instrumentItem.setAttribute('aria-selected', 'true');

            // Update state
            this.state.selectedInstrument = {
                id: instrumentItem.dataset.instrumentId,
                name: instrumentItem.dataset.instrumentName
            };
            this.state.currentlyPlayingUrl = null;

            // Reset search
            if (this.elements.searchInput) {
                this.elements.searchInput.value = '';
            }

            // Load songs for this instrument
            await this.loadSongsForInstrument(this.state.selectedInstrument.id);

            // Show search and song section
            if (this.elements.searchContainer) {
                this.elements.searchContainer.style.display = 'block';
            }
            this.elements.songSection.style.display = 'block';
        }

        async loadSongsForInstrument(instrumentId, searchQuery = '') {
            this.showLoading(this.elements.songList);
            
            try {
                const url = searchQuery 
                    ? `/charts/songs/${instrumentId}/?search=${encodeURIComponent(searchQuery)}`
                    : `/charts/songs/${instrumentId}/`;
                
                const response = await fetch(url);
                const data = await response.json();
                
                this.renderSongList(data.songs);
            } catch (error) {
                console.error('Error loading songs:', error);
                this.elements.songList.innerHTML = '<div class="selector-error">Error loading songs</div>';
            }
        }

        renderSongList(songs) {
            if (songs.length === 0) {
                this.elements.songList.innerHTML = '<div class="selector-empty">No songs found</div>';
                return;
            }

            const html = songs.map(song => {
                // Serialize video data and escape for double-quote attribute context
                const videosJson = JSON.stringify(song.videos || [])
                    .replace(/"/g, '&quot;');
                const chartsJson = JSON.stringify(song.charts || [])
                    .replace(/"/g, '&quot;');
                
                const hasSingleChart = song.charts && song.charts.length === 1;
                const hasMultipleCharts = song.charts && song.charts.length > 1;
                const pdfUrl = hasSingleChart ? song.charts[0].pdf_url : '';

                return `
                <div class="selector-item song-item" 
                     role="option"
                     data-song-id="${song.id}"
                     data-song-title="${this.escapeHtml(song.title)}"
                     data-has-recording="${song.has_recording}"
                     data-recording-url="${this.escapeHtml(song.recording_url || '')}"
                     data-has-video="${song.has_video}"
                     data-videos="${videosJson}"
                     data-has-multiple="${hasMultipleCharts}"
                     data-charts="${chartsJson}">
                    <span class="song-media-icons">
                        <span class="media-icon-slot">
                            ${song.has_recording ? `
                                <button class="song-play-btn" title="Play recording" aria-label="Play ${this.escapeHtml(song.title)}">
                                    <i class="fa fa-play-circle"></i>
                                </button>
                            ` : ''}
                        </span>
                        <span class="media-icon-slot">
                            ${song.has_video && song.videos.length === 1 ? `
                                <a href="${this.escapeHtml(song.videos[0].url)}" class="song-video-btn" target="_blank" rel="noopener" title="${this.escapeHtml(song.videos[0].title || 'Watch video')}" aria-label="Watch ${this.escapeHtml(song.title)} video">
                                    <i class="fa fa-youtube-play"></i>
                                </a>
                            ` : ''}
                            ${song.has_video && song.videos.length > 1 ? `
                                <div class="video-dropdown">
                                    <button class="song-video-btn video-dropdown-toggle" title="Watch videos" aria-label="Watch ${this.escapeHtml(song.title)} videos">
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
                            ` : ''}
                        </span>
                    </span>
                    <span class="selector-item-text">
                        ${this.escapeHtml(song.title)}
                    </span>
                    <span class="song-actions">
                        ${hasMultipleCharts ? '<i class="fa fa-chevron-right expand-icon"></i>' : ''}
                        ${pdfUrl ? `
                            <a href="${pdfUrl}" class="btn btn-sm btn-primary chart-pdf-btn" target="_blank" rel="noopener" title="Open Chart PDF">
                                <i class="fa fa-file-pdf-o"></i>
                                Open Chart PDF
                            </a>
                        ` : ''}
                    </span>
                </div>
            `;
            }).join('');

            this.elements.songList.innerHTML = html;
        }

        toggleSongParts(songItem) {
            const hasMultipleParts = songItem.dataset.hasMultiple === 'true';
            if (!hasMultipleParts) {
                return; // Single part songs handled by direct PDF button
            }

            // Check if already expanded
            const isExpanded = songItem.classList.contains('expanded');
            
            // Collapse all other songs and remove their parts
            this.elements.songList.querySelectorAll('.selector-item.expanded').forEach(item => {
                if (item !== songItem) {
                    item.classList.remove('expanded');
                    const expandIcon = item.querySelector('.expand-icon');
                    if (expandIcon) expandIcon.className = 'fa fa-chevron-right expand-icon';
                    // Remove parts after this song
                    let next = item.nextElementSibling;
                    while (next && next.classList.contains('part-item')) {
                        const toRemove = next;
                        next = next.nextElementSibling;
                        toRemove.remove();
                    }
                }
            });

            if (isExpanded) {
                // Collapse this song
                songItem.classList.remove('expanded');
                const expandIcon = songItem.querySelector('.expand-icon');
                if (expandIcon) expandIcon.className = 'fa fa-chevron-right expand-icon';
                // Remove parts
                let next = songItem.nextElementSibling;
                while (next && next.classList.contains('part-item')) {
                    const toRemove = next;
                    next = next.nextElementSibling;
                    toRemove.remove();
                }
            } else {
                // Expand this song
                songItem.classList.add('expanded');
                const expandIcon = songItem.querySelector('.expand-icon');
                if (expandIcon) expandIcon.className = 'fa fa-chevron-down expand-icon';
                
                // Get charts from data attribute
                try {
                    const charts = JSON.parse(songItem.dataset.charts || '[]');
                    
                    if (charts.length > 0) {
                        // Create part items
                        const partsHtml = charts.map(chart => `
                            <div class="selector-item part-item"
                                 role="option"
                                 data-chart-id="${chart.id}"
                                 data-part-name="${this.escapeHtml(chart.part)}">
                                <span class="song-media-icons"></span>
                                <span class="selector-item-text">${this.escapeHtml(chart.part)}</span>
                                <span class="song-actions">
                                    ${chart.pdf_url ? `
                                        <a href="${chart.pdf_url}" class="btn btn-sm btn-primary chart-pdf-btn" target="_blank" rel="noopener" title="Open Chart PDF">
                                            <i class="fa fa-file-pdf-o"></i>
                                            Open Chart PDF
                                        </a>
                                    ` : ''}
                                </span>
                            </div>
                        `).join('');
                        
                        // Insert parts after the song
                        songItem.insertAdjacentHTML('afterend', partsHtml);
                    }
                } catch (error) {
                    console.error('Error parsing charts:', error);
                }
            }
        }

        toggleSection(sectionHeader) {
            const sectionGroup = sectionHeader.closest('.section-group');
            if (sectionGroup) {
                sectionGroup.classList.toggle('collapsed');
            }
        }

        playSong(songItem) {
            const recordingUrl = songItem.dataset.recordingUrl;
            const songTitle = songItem.dataset.songTitle;

            if (!recordingUrl) return;

            const playBtn = songItem.querySelector('.song-play-btn');
            const isCurrentSong = this.state.currentlyPlayingUrl === recordingUrl;
            const isPlaying = !this.elements.audioElement.paused;

            // Toggle play/pause if clicking the current song
            if (isCurrentSong) {
                if (isPlaying) {
                    this.elements.audioElement.pause();
                    if (playBtn) {
                        playBtn.classList.remove('playing');
                        playBtn.querySelector('i').className = 'fa fa-play-circle';
                    }
                } else {
                    this.elements.audioElement.play().catch(err => {
                        console.error('Error playing audio:', err);
                    });
                    if (playBtn) {
                        playBtn.classList.add('playing');
                        playBtn.querySelector('i').className = 'fa fa-pause-circle';
                    }
                }
                return;
            }

            // Different song - load and play
            this.state.currentlyPlayingUrl = recordingUrl;
            this.elements.audioElement.src = recordingUrl;
            this.elements.nowPlayingTitle.textContent = songTitle;
            
            // Update video links visibility
            const videoLinksContainer = this.elements.audioPlayer.querySelector('.video-links');
            let videos = [];
            try {
                videos = JSON.parse(songItem.dataset.videos || '[]');
            } catch (e) {
                videos = [];
            }
            
            if (videoLinksContainer) {
                if (videos.length > 0) {
                    const linksHtml = videos.map((v, i) => {
                        const videoUrl = this.escapeHtml(v.url);
                        const videoTitle = this.escapeHtml(v.title || 'Video ' + (i + 1));
                        const displayLabel = videos.length > 1 ? ' ' + videoTitle : '';
                        return `<a href="${videoUrl}" class="video-link" target="_blank" rel="noopener" title="${videoTitle}">
                            <i class="fa fa-youtube-play"></i>${displayLabel}
                        </a>`;
                    }).join('');
                    videoLinksContainer.innerHTML = linksHtml;
                    videoLinksContainer.style.display = 'flex';
                } else {
                    videoLinksContainer.innerHTML = '';
                    videoLinksContainer.style.display = 'none';
                }
            }

            // Show audio player and play
            this.elements.audioPlayer.style.display = 'block';
            this.elements.audioElement.play().catch(err => {
                console.error('Error playing audio:', err);
            });

            // Update play button states
            this.elements.songList.querySelectorAll('.song-play-btn').forEach(btn => {
                btn.classList.remove('playing');
                btn.querySelector('i').className = 'fa fa-play-circle';
            });
            
            if (playBtn) {
                playBtn.classList.add('playing');
                playBtn.querySelector('i').className = 'fa fa-pause-circle';
            }

            // Handle audio events
            this.elements.audioElement.onended = () => {
                if (playBtn) {
                    playBtn.classList.remove('playing');
                    playBtn.querySelector('i').className = 'fa fa-play-circle';
                }
            };

            this.elements.audioElement.onpause = () => {
                if (playBtn) {
                    playBtn.classList.remove('playing');
                    playBtn.querySelector('i').className = 'fa fa-play-circle';
                }
            };
        }

        showLoading(element) {
            element.innerHTML = `
                <div class="selector-loading">
                    <span class="spinner-border spinner-border-sm" role="status"></span>
                    Loading...
                </div>
            `;
        }

        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            const escaped = div.innerHTML;
            return escaped
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
