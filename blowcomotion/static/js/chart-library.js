/**
 * Chart Library Block JavaScript
 * 
 * Handles:
 * - Song search with debounce
 * - Cascading selection (song → instrument → part)
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
                selectedSong: null,
                selectedInstrument: null,
                selectedChart: null
            };

            // Cache DOM elements
            this.elements = {
                searchInput: container.querySelector('.chart-search-input'),
                songList: container.querySelector('.song-list'),
                instrumentSection: container.querySelector('.instrument-section'),
                instrumentList: container.querySelector('.instrument-list'),
                partSection: container.querySelector('.part-section'),
                partList: container.querySelector('.part-list'),
                audioPlayer: container.querySelector('.chart-audio-player'),
                audioElement: container.querySelector('.chart-audio-element'),
                nowPlayingTitle: container.querySelector('.now-playing-title'),
                chartPlaceholder: container.querySelector('.chart-placeholder'),
                chartDetails: container.querySelector('.chart-details'),
                chartSongTitle: container.querySelector('.chart-song-title'),
                chartInstrumentPart: container.querySelector('.chart-instrument-part'),
                chartPdfLink: container.querySelector('.chart-pdf-link')
            };

            this.init();
        }

        init() {
            this.bindEvents();
            this.loadSongs();
        }

        bindEvents() {
            // Search input with debounce
            if (this.elements.searchInput) {
                const debouncedSearch = debounce((query) => {
                    this.loadSongs(query);
                }, 300);

                this.elements.searchInput.addEventListener('input', (e) => {
                    debouncedSearch(e.target.value);
                });
            }

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

                // Handle song item selection
                const songItem = e.target.closest('.selector-item');
                if (songItem) {
                    this.selectSong(songItem);
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

            // Instrument list click delegation
            this.elements.instrumentList.addEventListener('click', (e) => {
                const instrumentItem = e.target.closest('.selector-item');
                if (instrumentItem) {
                    this.selectInstrument(instrumentItem);
                }
            });

            // Part list click delegation
            this.elements.partList.addEventListener('click', (e) => {
                const partItem = e.target.closest('.selector-item');
                if (partItem) {
                    this.selectPart(partItem);
                }
            });
        }

        async loadSongs(searchQuery = '') {
            this.showLoading(this.elements.songList);
            
            try {
                const url = searchQuery 
                    ? `/charts/songs/?search=${encodeURIComponent(searchQuery)}`
                    : '/charts/songs/';
                
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

            const html = songs.map(song => `
                <div class="selector-item" 
                     role="option"
                     data-song-id="${song.id}"
                     data-song-title="${this.escapeHtml(song.title)}"
                     data-has-recording="${song.has_recording}"
                     data-recording-url="${song.recording_url || ''}"
                     data-has-video="${song.has_video}"
                     data-videos='${JSON.stringify(song.videos || [])}'>
                    <span class="selector-item-text">${this.escapeHtml(song.title)}</span>
                    <span class="song-media-buttons">
                        ${song.has_recording ? `
                            <button class="song-play-btn" title="Play recording" aria-label="Play ${this.escapeHtml(song.title)}">
                                <i class="fa fa-play-circle"></i>
                            </button>
                        ` : ''}
                        ${song.has_video && song.videos.length === 1 ? `
                            <a href="${song.videos[0].url}" class="song-video-btn" target="_blank" rel="noopener" title="${song.videos[0].title || 'Watch video'}" aria-label="Watch ${this.escapeHtml(song.title)} video">
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
                                        <a href="${v.url}" class="video-dropdown-item" target="_blank" rel="noopener">
                                            <i class="fa fa-play"></i> ${v.title || 'Video ' + (i + 1)}
                                        </a>
                                    `).join('')}
                                </div>
                            </div>
                        ` : ''}
                    </span>
                </div>
            `).join('');

            this.elements.songList.innerHTML = html;
        }

        async selectSong(songItem) {
            // Update UI state
            this.elements.songList.querySelectorAll('.selector-item').forEach(item => {
                item.classList.remove('active');
                item.setAttribute('aria-selected', 'false');
            });
            songItem.classList.add('active');
            songItem.setAttribute('aria-selected', 'true');

            // Update state
            this.state.selectedSong = {
                id: songItem.dataset.songId,
                title: songItem.dataset.songTitle,
                hasRecording: songItem.dataset.hasRecording === 'true',
                recordingUrl: songItem.dataset.recordingUrl
            };
            this.state.selectedInstrument = null;
            this.state.selectedChart = null;

            // Reset downstream selections
            this.elements.partSection.style.display = 'none';
            this.elements.partList.innerHTML = '';
            this.hideChartDetails();

            // Load instruments for this song
            this.showLoading(this.elements.instrumentList);
            this.elements.instrumentSection.style.display = 'block';

            try {
                const response = await fetch(`/charts/instruments/${this.state.selectedSong.id}/`);
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
                <div class="section-group">
                    <div class="section-header">${this.escapeHtml(section.name)}</div>
                    ${section.instruments.map(instrument => `
                        <div class="selector-item"
                             role="option"
                             data-instrument-id="${instrument.id}"
                             data-instrument-name="${this.escapeHtml(instrument.name)}">
                            <span class="selector-item-text">${this.escapeHtml(instrument.name)}</span>
                        </div>
                    `).join('')}
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
            this.state.selectedChart = null;

            // Load charts for this song+instrument
            try {
                const response = await fetch(
                    `/charts/parts/${this.state.selectedSong.id}/${this.state.selectedInstrument.id}/`
                );
                const data = await response.json();
                
                if (data.charts.length === 1) {
                    // Auto-select if only one part
                    this.elements.partSection.style.display = 'none';
                    this.displayChart(data.charts[0]);
                } else if (data.charts.length > 1) {
                    // Show part selector
                    this.elements.partSection.style.display = 'block';
                    this.renderPartList(data.charts);
                    this.hideChartDetails();
                } else {
                    this.elements.partSection.style.display = 'none';
                    this.hideChartDetails();
                }
            } catch (error) {
                console.error('Error loading charts:', error);
                this.elements.partSection.style.display = 'none';
            }
        }

        renderPartList(charts) {
            const html = charts.map(chart => `
                <div class="selector-item"
                     role="option"
                     data-chart-id="${chart.id}"
                     data-part-name="${this.escapeHtml(chart.part)}"
                     data-pdf-url="${chart.pdf_url || ''}"
                     data-pdf-title="${this.escapeHtml(chart.pdf_title || '')}">
                    <span class="selector-item-text">${this.escapeHtml(chart.part)}</span>
                </div>
            `).join('');

            this.elements.partList.innerHTML = html;
        }

        selectPart(partItem) {
            // Update UI state
            this.elements.partList.querySelectorAll('.selector-item').forEach(item => {
                item.classList.remove('active');
                item.setAttribute('aria-selected', 'false');
            });
            partItem.classList.add('active');
            partItem.setAttribute('aria-selected', 'true');

            // Display the chart
            this.displayChart({
                id: partItem.dataset.chartId,
                part: partItem.dataset.partName,
                pdf_url: partItem.dataset.pdfUrl,
                pdf_title: partItem.dataset.pdfTitle
            });
        }

        displayChart(chart) {
            this.state.selectedChart = chart;

            // Update chart display
            this.elements.chartSongTitle.textContent = this.state.selectedSong.title;
            
            const partText = this.state.selectedInstrument.name;
            const fullPartText = chart.part !== this.state.selectedInstrument.name 
                ? `${partText} - ${chart.part}`
                : partText;
            this.elements.chartInstrumentPart.textContent = fullPartText;

            if (chart.pdf_url) {
                this.elements.chartPdfLink.href = chart.pdf_url;
                this.elements.chartPdfLink.style.display = 'inline-block';
            } else {
                this.elements.chartPdfLink.style.display = 'none';
            }

            // Show chart details, hide placeholder
            this.elements.chartPlaceholder.style.display = 'none';
            this.elements.chartDetails.style.display = 'block';
        }

        hideChartDetails() {
            this.elements.chartPlaceholder.style.display = 'flex';
            this.elements.chartDetails.style.display = 'none';
        }

        playSong(songItem) {
            const recordingUrl = songItem.dataset.recordingUrl;
            const songTitle = songItem.dataset.songTitle;

            if (!recordingUrl) return;

            // Update audio element
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
                    const linksHtml = videos.map((v, i) => 
                        `<a href="${v.url}" class="video-link" target="_blank" rel="noopener" title="${v.title || 'Watch Video'}">
                            <i class="fa fa-youtube-play"></i>${videos.length > 1 ? ' ' + (v.title || 'Video ' + (i + 1)) : ''}
                        </a>`
                    ).join('');
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
            
            const playBtn = songItem.querySelector('.song-play-btn');
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
            return div.innerHTML;
        }
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initChartLibraryBlocks);
    } else {
        initChartLibraryBlocks();
    }
})();
