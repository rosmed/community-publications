const { createApp } = Vue;

createApp({
    data() {
        return {
            publications: [],
            totalAuthors: 0,
            chartInstances: {},
        };
    },
    computed: {
        totalPublications() {
            return this.publications.length;
        },
        yearRangeText() {
            const years = this.publications.map(p => parseInt(p.year)).filter(Boolean);
            if (!years.length) return '';
            const min = Math.min(...years);
            const max = Math.max(...years);
            return `${min} – ${max}`;
        },
        countSlicer() {
            return this.publications.filter(p => p.package && p.package.includes('slicer_ros2')).length;
        },
        countIgtl() {
            return this.publications.filter(p => p.package && p.package.includes('ros2_igtl')).length;
        }
    },
    methods: {
        async loadData() {
            try {
                await CONFIG.init();
                const res = await fetch('publications.bib');
                const text = await res.text();
                const cleaned = CONFIG.cleanBibtexText(text);
                const parsed = bibtexParse.toJSON(cleaned);

                this.publications = parsed
                    .filter(entry => entry.entryTags && entry.entryTags.title)
                    .map(entry => {
                        const tags = entry.entryTags;
                        return {
                            id: entry.citationKey,
                            type: (entry.entryType || 'article').toLowerCase(),
                            title: CONFIG.convertLatexToUnicode(tags.title || ''),
                            author: CONFIG.convertLatexToUnicode(tags.author || ''),
                            year: tags.year || '',
                            journal: CONFIG.convertLatexToUnicode(tags.journal || tags.booktitle || tags.school || ''),
                            package: (tags.package || '').replace(/[{}]/g, '').trim(),
                        };
                    });

                this.totalAuthors = CONFIG.calculateTotalAuthors(this.publications);

                this.$nextTick(() => {
                    this.renderCharts();
                });
            } catch (err) {
                console.error('Error loading analytics data:', err);
            }
        },

        isDarkMode() {
            return document.documentElement.getAttribute('data-theme') === 'dark';
        },

        getChartColors() {
            const dark = this.isDarkMode();
            return {
                text: dark ? '#cbd5e1' : '#475569',
                grid: dark ? '#233554' : '#e2e8f0',
                primary: '#0284c7',
                slicer: '#0d9488',
                igtl: '#7c3aed',
                accent: '#6366f1',
                colors: [
                    '#0284c7', '#0d9488', '#7c3aed', '#f59e0b', '#ec4899', '#10b981', '#6366f1'
                ]
            };
        },

        renderCharts() {
            this.destroyCharts();
            const colors = this.getChartColors();

            // 1. Publications by Year
            const yearCounts = {};
            this.publications.forEach(p => {
                if (p.year) yearCounts[p.year] = (yearCounts[p.year] || 0) + 1;
            });
            const sortedYears = Object.keys(yearCounts).sort();

            const ctxYear = document.getElementById('chartYear');
            if (ctxYear) {
                this.chartInstances.year = new Chart(ctxYear, {
                    type: 'bar',
                    data: {
                        labels: sortedYears,
                        datasets: [{
                            label: 'Publications',
                            data: sortedYears.map(y => yearCounts[y]),
                            backgroundColor: colors.primary,
                            borderRadius: 4,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            x: {
                                ticks: { color: colors.text },
                                grid: { color: colors.grid }
                            },
                            y: {
                                ticks: { color: colors.text, stepSize: 1 },
                                grid: { color: colors.grid }
                            }
                        }
                    }
                });
            }

            // 2. Breakdown by Package
            const ctxPkg = document.getElementById('chartPackage');
            if (ctxPkg) {
                this.chartInstances.pkg = new Chart(ctxPkg, {
                    type: 'doughnut',
                    data: {
                        labels: ['SlicerROS2 Only', 'ros2_igtl_bridge Only', 'Both / Interoperable'],
                        datasets: [{
                            data: [
                                this.publications.filter(p => p.package === 'slicer_ros2').length,
                                this.publications.filter(p => p.package === 'ros2_igtl').length,
                                this.publications.filter(p => p.package && p.package.includes('slicer_ros2') && p.package.includes('ros2_igtl')).length,
                            ],
                            backgroundColor: [colors.slicer, colors.igtl, colors.primary],
                            borderWidth: 0,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { color: colors.text }
                            }
                        }
                    }
                });
            }

            // 3. Publication Types
            const typeCounts = {};
            const typeLabels = {
                'article': 'Journal Article',
                'inproceedings': 'Conference Paper',
                'phdthesis': 'PhD Thesis',
                'misc': 'Preprint / Report'
            };
            this.publications.forEach(p => {
                const label = typeLabels[p.type] || p.type;
                typeCounts[label] = (typeCounts[label] || 0) + 1;
            });

            const ctxType = document.getElementById('chartType');
            if (ctxType) {
                this.chartInstances.type = new Chart(ctxType, {
                    type: 'pie',
                    data: {
                        labels: Object.keys(typeCounts),
                        datasets: [{
                            data: Object.values(typeCounts),
                            backgroundColor: colors.colors,
                            borderWidth: 0,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { color: colors.text }
                            }
                        }
                    }
                });
            }

            // 4. Top Venues
            const venueCounts = {};
            this.publications.forEach(p => {
                let v = p.journal.trim();
                if (!v) return;
                // Normalize some venues
                if (v.includes('Hamlyn')) v = 'Hamlyn Symposium (HSMR)';
                if (v.includes('Medical Robotics and Bionics')) v = 'IEEE TMRB';
                if (v.includes('Computer Assisted Radiology')) v = 'IJCARS';
                if (v.includes('Sensors')) v = 'MDPI Sensors';
                if (v.includes('arXiv')) v = 'arXiv Preprints';
                if (v.includes('SPIE') || v.includes('Medical Imaging 2025')) v = 'SPIE Medical Imaging';
                venueCounts[v] = (venueCounts[v] || 0) + 1;
            });

            const topVenues = Object.entries(venueCounts)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 7);

            const ctxVenue = document.getElementById('chartVenue');
            if (ctxVenue) {
                this.chartInstances.venue = new Chart(ctxVenue, {
                    type: 'bar',
                    data: {
                        labels: topVenues.map(x => x[0]),
                        datasets: [{
                            label: 'Papers',
                            data: topVenues.map(x => x[1]),
                            backgroundColor: colors.accent,
                            borderRadius: 4,
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            x: {
                                ticks: { color: colors.text, stepSize: 1 },
                                grid: { color: colors.grid }
                            },
                            y: {
                                ticks: { color: colors.text, font: { size: 11 } },
                                grid: { color: colors.grid }
                            }
                        }
                    }
                });
            }
        },

        destroyCharts() {
            Object.values(this.chartInstances).forEach(c => {
                if (c) c.destroy();
            });
            this.chartInstances = {};
        }
    },
    mounted() {
        this.loadData();
        window.addEventListener('theme-changed', () => {
            this.renderCharts();
        });
    }
}).mount('#app');
