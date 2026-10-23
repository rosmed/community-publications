const { createApp } = Vue;

createApp({
    data() {
        return {
            publications: [],
            searchQuery: '',
            searchInAbstract: false,
            selectedLibrary: '',
            selectedType: '',
            startYear: '',
            endYear: '',
            sortBy: 'year_desc',
            currentPage: 1,
            itemsPerPage: 25,
            publicationMap: {}
        };
    },
    computed: {
        availableYears() {
            const years = [...new Set(this.publications.map(p => p.year).filter(Boolean))];
            return years.sort((a, b) => b - a);
        },
        availableStartYears() {
            if (!this.endYear) return this.availableYears;
            return this.availableYears.filter(year => parseInt(year) <= parseInt(this.endYear));
        },
        availableEndYears() {
            if (!this.startYear) return this.availableYears;
            return this.availableYears.filter(year => parseInt(year) >= parseInt(this.startYear));
        },
        filteredPublications() {
            let filtered = this.publications;

            // Library filter (rosmed_library)
            if (this.selectedLibrary) {
                filtered = filtered.filter(pub => {
                    if (!pub.rosmed_library) return false;
                    const libs = pub.rosmed_library.split(' and ').map(p => p.trim());
                    return libs.includes(this.selectedLibrary);
                });
            }

            // Type filter
            if (this.selectedType) {
                filtered = filtered.filter(pub => pub.type.toLowerCase() === this.selectedType.toLowerCase());
            }

            // Year filter
            if (this.startYear) {
                filtered = filtered.filter(pub => parseInt(pub.year) >= parseInt(this.startYear));
            }
            if (this.endYear) {
                filtered = filtered.filter(pub => parseInt(pub.year) <= parseInt(this.endYear));
            }

            // Search filter
            if (this.searchQuery) {
                const q = this.searchQuery.toLowerCase().trim();
                filtered = filtered.filter(pub => {
                    const matchesBasic = (
                        pub.title?.toLowerCase().includes(q) ||
                        pub.author?.toLowerCase().includes(q) ||
                        pub.journal?.toLowerCase().includes(q) ||
                        pub.booktitle?.toLowerCase().includes(q) ||
                        pub.school?.toLowerCase().includes(q) ||
                        pub.id?.toLowerCase().includes(q)
                    );
                    if (matchesBasic) return true;
                    if (this.searchInAbstract && pub.abstract) {
                        return pub.abstract.toLowerCase().includes(q);
                    }
                    return false;
                });
            }

            // Sorting
            const sorted = [...filtered];
            switch (this.sortBy) {
                case 'year_asc':
                    sorted.sort((a, b) => {
                        const diff = CONFIG.getPublicationDateSortKey(a) - CONFIG.getPublicationDateSortKey(b);
                        return diff !== 0 ? diff : (a.title || '').localeCompare(b.title || '');
                    });
                    break;
                case 'date_added_desc':
                    sorted.sort((a, b) => {
                        const dateDiff = (b.date_added || '').localeCompare(a.date_added || '');
                        if (dateDiff !== 0) return dateDiff;
                        return CONFIG.getPublicationDateSortKey(b) - CONFIG.getPublicationDateSortKey(a);
                    });
                    break;
                case 'title_asc':
                    sorted.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
                    break;
                case 'author_asc':
                    sorted.sort((a, b) => (a.author || '').localeCompare(b.author || ''));
                    break;
                case 'year_desc':
                default:
                    sorted.sort((a, b) => {
                        const diff = CONFIG.getPublicationDateSortKey(b) - CONFIG.getPublicationDateSortKey(a);
                        return diff !== 0 ? diff : (a.title || '').localeCompare(b.title || '');
                    });
                    break;
            }

            return sorted;
        },
        paginatedPublications() {
            const start = (this.currentPage - 1) * this.itemsPerPage;
            return this.filteredPublications.slice(start, start + this.itemsPerPage);
        },
        totalPages() {
            return Math.ceil(this.filteredPublications.length / this.itemsPerPage) || 1;
        },
        totalAuthors() {
            return CONFIG.calculateTotalAuthors(this.filteredPublications);
        },
        countSlicerRos2() {
            return this.publications.filter(p => p.rosmed_library && p.rosmed_library.includes('SlicerROS2')).length;
        },
        countRos2Igtl() {
            return this.publications.filter(p => p.rosmed_library && p.rosmed_library.includes('ROS2_IGTL')).length;
        },
        countRosIgtl() {
            return this.publications.filter(p => p.rosmed_library && p.rosmed_library.includes('ROS_IGTL')).length;
        }
    },
    methods: {
        async loadPublications() {
            try {
                await CONFIG.init();
                const response = await fetch('publications.bib');
                const bibtexText = await response.text();

                const cleaned = CONFIG.cleanBibtexText(bibtexText);
                const parsed = bibtexParse.toJSON(cleaned);
                const rawEntries = this.extractBibtexEntries(cleaned);

                this.publications = parsed
                    .filter(entry => entry.entryTags && entry.entryTags.title)
                    .map(entry => {
                        const tags = entry.entryTags;
                        const key = entry.citationKey;
                        const lib = (tags.rosmed_library || tags.package || '').replace(/[{}]/g, '').trim();

                        return {
                            id: key,
                            type: entry.entryType || 'article',
                            title: CONFIG.convertLatexToUnicode(tags.title || ''),
                            author: CONFIG.convertLatexToUnicode(tags.author || ''),
                            year: tags.year || '',
                            month: tags.month || '',
                            journal: CONFIG.convertLatexToUnicode(tags.journal || ''),
                            booktitle: CONFIG.convertLatexToUnicode(tags.booktitle || ''),
                            school: CONFIG.convertLatexToUnicode(tags.school || ''),
                            volume: tags.volume || '',
                            number: tags.number || '',
                            pages: tags.pages || '',
                            doi: tags.doi || '',
                            url: tags.url || '',
                            arxiv: tags.arxiv || tags.eprint || '',
                            openaccesspdf: tags.openaccesspdf || '',
                            abstract: CONFIG.convertLatexToUnicode(tags.abstract || ''),
                            rosmed_library: lib,
                            date_added: (tags.date_added || '').replace(/[{}]/g, ''),
                            bibtexText: rawEntries[key] || '',
                            showAbstract: false,
                            showBibtex: false,
                            showRis: false,
                            showCite: false,
                            copiedBib: false,
                            copiedRis: false,
                            copiedCite: false,
                            copiedLink: false,
                            isHighlighted: false
                        };
                    })
                    .sort((a, b) => CONFIG.getPublicationDateSortKey(b) - CONFIG.getPublicationDateSortKey(a));

                this.publicationMap = {};
                this.publications.forEach(p => {
                    this.publicationMap[p.id] = p;
                });

                if (this.availableYears.length > 0) {
                    this.startYear = this.availableYears[this.availableYears.length - 1];
                    this.endYear = this.availableYears[0];
                }

                this.$nextTick(() => {
                    this.handleHashNavigation();
                });

            } catch (err) {
                console.error('Failed to load publications:', err);
            }
        },

        extractBibtexEntries(bibtexText) {
            const entries = {};
            const regex = /@(\w+)\s*\{\s*([^,]+),[\s\S]*?\n\}/g;
            let match;
            while ((match = regex.exec(bibtexText)) !== null) {
                entries[match[2].trim()] = match[0].trim();
            }
            return entries;
        },

        formatAuthors(authorsStr) {
            if (!authorsStr) return '';
            const authors = CONFIG.parseAuthorList(authorsStr);
            if (authors.length <= 4) {
                return authors.map(a => `${a.first} ${a.last}`.trim()).join(', ');
            }
            const firstThree = authors.slice(0, 3).map(a => `${a.first} ${a.last}`.trim()).join(', ');
            return `${firstThree}, et al. (${authors.length} authors)`;
        },

        formatType(type) {
            const map = {
                'article': 'Journal Article',
                'inproceedings': 'Conference Paper',
                'incollection': 'Book Chapter',
                'phdthesis': 'PhD Thesis',
                'mastersthesis': "Master's Thesis",
                'misc': 'Preprint / Report'
            };
            return map[type.toLowerCase()] || type;
        },

        parseLibraries(libStr) {
            if (!libStr) return [];
            return libStr.split(' and ').map(p => p.trim()).filter(Boolean);
        },

        libraryName(id) {
            return CONFIG.LIBRARY_MAP[id] || id;
        },

        libraryBadgeClass(id) {
            if (id === 'SlicerROS2') return 'badge-slicer';
            if (id === 'ROS2_IGTL') return 'badge-ros2-igtl';
            if (id === 'ROS_IGTL') return 'badge-ros-igtl';
            return 'badge-type';
        },

        toggleAbstract(pub) {
            pub.showAbstract = !pub.showAbstract;
            if (pub.showAbstract) {
                pub.showBibtex = false;
                pub.showRis = false;
                pub.showCite = false;
            }
        },

        toggleBibtex(pub) {
            pub.showBibtex = !pub.showBibtex;
            if (pub.showBibtex) {
                pub.showAbstract = false;
                pub.showRis = false;
                pub.showCite = false;
            }
        },

        toggleRis(pub) {
            pub.showRis = !pub.showRis;
            if (pub.showRis) {
                pub.showAbstract = false;
                pub.showBibtex = false;
                pub.showCite = false;
            }
        },

        toggleCite(pub) {
            pub.showCite = !pub.showCite;
            if (pub.showCite) {
                pub.showAbstract = false;
                pub.showBibtex = false;
                pub.showRis = false;
            }
        },

        getRisText(pub) {
            return CONFIG.generateRis(pub);
        },

        getApaText(pub) {
            return CONFIG.formatApa(pub);
        },

        getIeeeText(pub) {
            return CONFIG.formatIeee(pub);
        },

        async copyText(text, pub, field) {
            try {
                await navigator.clipboard.writeText(text);
                pub[field] = true;
                setTimeout(() => {
                    pub[field] = false;
                }, 2000);
            } catch (err) {
                console.error('Copy failed:', err);
            }
        },

        async sharePublication(pub) {
            const url = `${window.location.origin}${window.location.pathname}#${pub.id}`;
            await this.copyText(url, pub, 'copiedLink');
        },

        downloadSingleBibtex(pub) {
            const blob = new Blob([pub.bibtexText || ''], { type: 'text/plain;charset=utf-8' });
            this.triggerDownload(blob, `${pub.id}.bib`);
        },

        downloadBibtex() {
            const allText = this.filteredPublications.map(p => p.bibtexText).filter(Boolean).join('\n\n');
            const blob = new Blob([allText], { type: 'text/plain;charset=utf-8' });
            this.triggerDownload(blob, 'rosmed_publications.bib');
        },

        downloadRis(pub) {
            const ris = CONFIG.generateRis(pub);
            const blob = new Blob([ris], { type: 'application/x-research-info-systems;charset=utf-8' });
            this.triggerDownload(blob, `${pub.id}.ris`);
        },

        downloadAllRis() {
            const allRis = this.filteredPublications.map(p => CONFIG.generateRis(p)).join('\r\n\r\n');
            const blob = new Blob([allRis], { type: 'application/x-research-info-systems;charset=utf-8' });
            this.triggerDownload(blob, 'rosmed_publications.ris');
        },

        triggerDownload(blob, filename) {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        },

        resetFilters() {
            this.searchQuery = '';
            this.searchInAbstract = false;
            this.selectedLibrary = '';
            this.selectedType = '';
            if (this.availableYears.length > 0) {
                this.startYear = this.availableYears[this.availableYears.length - 1];
                this.endYear = this.availableYears[0];
            }
            this.sortBy = 'year_desc';
            this.currentPage = 1;
        },

        handleHashNavigation() {
            const hash = window.location.hash.substring(1);
            if (!hash) return;
            const target = this.publicationMap[hash];
            if (target) {
                const index = this.filteredPublications.findIndex(p => p.id === hash);
                if (index !== -1) {
                    this.currentPage = Math.floor(index / this.itemsPerPage) + 1;
                }
                this.$nextTick(() => {
                    const el = document.getElementById(hash);
                    if (el) {
                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        target.isHighlighted = true;
                        setTimeout(() => { target.isHighlighted = false; }, 3000);
                    }
                });
            }
        }
    },
    mounted() {
        this.loadPublications();
        window.addEventListener('hashchange', () => this.handleHashNavigation());
    }
}).mount('#app');
