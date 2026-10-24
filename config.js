// Configuration and shared utility functions for SlicerROS2 & ROS-IGTL Community Publications

const CONFIG = {
    LIBRARY_MAP: {},
    LIBRARY_DESCRIPTIONS: {},

    async init() {
        try {
            const response = await fetch('custom_tags.json');
            const data = await response.json();
            if (data.rosmed_libraries) {
                data.rosmed_libraries.forEach(lib => {
                    this.LIBRARY_MAP[lib.id] = lib.name;
                    this.LIBRARY_DESCRIPTIONS[lib.id] = lib.description;
                });
            }
            return true;
        } catch (error) {
            this.LIBRARY_MAP = {
                'SlicerROS2': 'SlicerROS2',
                'ROS2_IGTL': 'ROS2-IGTL-Bridge',
                'ROS_IGTL': 'ROS-IGTL-Bridge',
                'ROS2_IGTL_Bridge': 'ROS2-IGTL-Bridge',
                'ROS_IGTL_Bridge': 'ROS-IGTL-Bridge',
                'ros2_igtl_bridge': 'ROS2-IGTL-Bridge',
                'ros_igtl_bridge': 'ROS-IGTL-Bridge',
                'ROS2-IGTL-Bridge': 'ROS2-IGTL-Bridge',
                'ROS-IGTL-Bridge': 'ROS-IGTL-Bridge'
            };
            this.LIBRARY_DESCRIPTIONS = {
                'SlicerROS2': '3D Slicer module providing native ROS 2 node communication, tf2 tracking, and robot rendering.',
                'ROS2_IGTL': 'ROS 2 OpenIGTLink bridge node (ROS2-IGTL-Bridge) for streaming medical data and tracking.',
                'ROS_IGTL': 'The original ROS 1 OpenIGTLink bridge (ROS-IGTL-Bridge) for image-guided therapy.'
            };
            return false;
        }
    },

    cleanBibtexText(text) {
        if (!text) return '';
        let result = '';
        let pos = 0;
        while (pos < text.length) {
            const nextComment = text.toLowerCase().indexOf('@comment', pos);
            if (nextComment === -1) {
                result += text.substring(pos);
                break;
            }
            result += text.substring(pos, nextComment);
            pos = nextComment + 8;
            while (pos < text.length && /\s/.test(text[pos])) pos++;
            if (pos < text.length && text[pos] === '{') {
                pos++;
                let braceCount = 1;
                while (pos < text.length && braceCount > 0) {
                    if (text[pos] === '@' && (pos === 0 || text[pos - 1] === '\n' || text[pos - 1] === '\r')) {
                        break;
                    }
                    if (text[pos] === '{') braceCount++;
                    else if (text[pos] === '}') braceCount--;
                    pos++;
                }
            }
        }
        return result;
    },

    convertLatexToUnicode(text) {
        if (!text) return '';
        const latexMap = {
            "'a": 'á', "'e": 'é', "'i": 'í', "'o": 'ó', "'u": 'ú',
            "'A": 'Á', "'E": 'É', "'I": 'Í', "'O": 'Ó', "'U": 'Ú',
            "'y": 'ý', "'Y": 'Ý', "'c": 'ć', "'C": 'Ć',
            "'n": 'ń', "'N": 'Ń', "'s": 'ś', "'S": 'Ś',
            "'z": 'ź', "'Z": 'Ź',
            "`a": 'à', "`e": 'è', "`i": 'ì', "`o": 'ò', "`u": 'ù',
            "`A": 'À', "`E": 'È', "`I": 'Ì', "`O": 'Ò', "`U": 'Ù',
            "^a": 'â', "^e": 'ê', "^i": 'î', "^o": 'ô', "^u": 'û',
            "^A": 'Â', "^E": 'Ê', "^I": 'Î', "^O": 'Ô', "^U": 'Û',
            "\"a": 'ä', "\"e": 'ë', "\"i": 'ï', "\"o": 'ö', "\"u": 'ü',
            "\"A": 'Ä', "\"E": 'Ë', "\"I": 'Ï', "\"O": 'Ö', "\"U": 'Ü',
            "~a": 'ã', "~o": 'õ', "~n": 'ñ',
            "~A": 'Ã', "~O": 'Õ', "~N": 'Ñ',
            "cc": 'ç', "cC": 'Ç', "c{c}": 'ç', "c{C}": 'Ç',
            "aa": 'å', "AA": 'Å',
            "oe": 'œ', "OE": 'Œ', "ae": 'æ', "AE": 'Æ',
            "ss": 'ß'
        };

        let result = text;
        for (const [latex, unicode] of Object.entries(latexMap)) {
            result = result.replace(new RegExp(`\\\\${latex}`, 'g'), unicode);
            result = result.replace(new RegExp(`\\\\\\{${latex}\\}`, 'g'), unicode);
        }
        result = result.replace(/\\&/g, '&');
        result = result.replace(/\\%/g, '%');
        result = result.replace(/\\_/g, '_');
        result = result.replace(/\\#/g, '#');
        result = result.replace(/[\{\}]/g, '');
        return result;
    },

    parseAuthorList(authorStr) {
        if (!authorStr) return [];
        return authorStr.split(' and ').map(raw => {
            raw = raw.trim();
            if (raw.includes(',')) {
                const parts = raw.split(',').map(p => p.trim());
                return { last: parts[0], first: parts.slice(1).join(' '), full: raw };
            } else {
                const parts = raw.split(' ').map(p => p.trim()).filter(Boolean);
                const last = parts.pop() || '';
                const first = parts.join(' ');
                return { last, first, full: raw };
            }
        });
    },

    getInitials(name) {
        if (!name) return '';
        return name.split(/[\s\.-]+/).filter(Boolean).map(p => p[0].toUpperCase() + '.').join(' ');
    },

    formatApa(pub) {
        const authors = this.parseAuthorList(pub.author);
        let authorStr = '';
        if (authors.length === 1) {
            authorStr = authors[0].last + (authors[0].first ? ', ' + this.getInitials(authors[0].first) : '');
        } else if (authors.length === 2) {
            authorStr = `${authors[0].last}, ${this.getInitials(authors[0].first)}, & ${authors[1].last}, ${this.getInitials(authors[1].first)}`;
        } else if (authors.length > 2) {
            const formatted = authors.map(a => a.last + (a.first ? ', ' + this.getInitials(a.first) : ''));
            if (formatted.length <= 20) {
                authorStr = formatted.slice(0, -1).join(', ') + ', & ' + formatted[formatted.length - 1];
            } else {
                authorStr = formatted.slice(0, 19).join(', ') + ', ... ' + formatted[formatted.length - 1];
            }
        }

        const yearStr = pub.year ? `(${pub.year}). ` : '';
        const titleStr = pub.title ? `${pub.title.replace(/\.$/, '')}. ` : '';
        let venueStr = '';
        if (pub.journal) {
            venueStr = pub.journal;
            if (pub.volume) venueStr += `, ${pub.volume}`;
            if (pub.number) venueStr += `(${pub.number})`;
            if (pub.pages) venueStr += `, ${pub.pages}`;
            venueStr += '. ';
        } else if (pub.booktitle) {
            venueStr = `In ${pub.booktitle}`;
            if (pub.pages) venueStr += ` (pp. ${pub.pages})`;
            if (pub.publisher) venueStr += `. ${pub.publisher}`;
            venueStr += '. ';
        } else if (pub.school) {
            venueStr = `PhD dissertation, ${pub.school}. `;
        }
        const doiStr = pub.doi ? `https://doi.org/${pub.doi}` : (pub.url || '');
        return ((authorStr ? authorStr + ' ' : '') + yearStr + titleStr + venueStr + doiStr).trim();
    },

    formatIeee(pub) {
        const authors = this.parseAuthorList(pub.author);
        let authorStr = '';
        if (authors.length === 1) {
            authorStr = (authors[0].first ? this.getInitials(authors[0].first) + ' ' : '') + authors[0].last;
        } else if (authors.length === 2) {
            authorStr = (authors[0].first ? this.getInitials(authors[0].first) + ' ' : '') + authors[0].last + ' and ' +
                        (authors[1].first ? this.getInitials(authors[1].first) + ' ' : '') + authors[1].last;
        } else if (authors.length > 6) {
            authorStr = (authors[0].first ? this.getInitials(authors[0].first) + ' ' : '') + authors[0].last + ' et al.';
        } else if (authors.length > 2) {
            const formatted = authors.map(a => (a.first ? this.getInitials(a.first) + ' ' : '') + a.last);
            authorStr = formatted.slice(0, -1).join(', ') + ', and ' + formatted[formatted.length - 1];
        }

        const titleStr = pub.title ? `"${pub.title.replace(/[.,]$/, '')},"` : '';
        let venueStr = '';
        if (pub.journal) {
            venueStr = pub.journal;
            if (pub.volume) venueStr += `, vol. ${pub.volume}`;
            if (pub.number) venueStr += `, no. ${pub.number}`;
            if (pub.pages) venueStr += `, pp. ${pub.pages}`;
            if (pub.year) venueStr += `, ${pub.year}`;
            venueStr += '.';
        } else if (pub.booktitle) {
            venueStr = `in ${pub.booktitle}`;
            if (pub.year) venueStr += `, ${pub.year}`;
            if (pub.pages) venueStr += `, pp. ${pub.pages}`;
            venueStr += '.';
        } else if (pub.school) {
            venueStr = `PhD dissertation, ${pub.school}, ${pub.year}.`;
        } else if (pub.year) {
            venueStr = `${pub.year}.`;
        }

        const doiStr = pub.doi ? ` doi: ${pub.doi}.` : '';
        return [authorStr, titleStr, venueStr].filter(Boolean).join(' ') + doiStr;
    },

    generateRis(pub) {
        const lines = [];
        const typeMap = {
            'article': 'JOUR',
            'inproceedings': 'CONF',
            'incollection': 'CHAP',
            'book': 'BOOK',
            'phdthesis': 'THES',
            'mastersthesis': 'THES',
            'techreport': 'RPRT',
            'misc': 'GEN'
        };
        lines.push('TY  - ' + (typeMap[pub.type?.toLowerCase()] || 'GEN'));
        if (pub.title) lines.push('TI  - ' + pub.title);
        const authors = this.parseAuthorList(pub.author);
        authors.forEach(a => lines.push('AU  - ' + a.last + (a.first ? ', ' + a.first : '')));
        if (pub.year) lines.push('PY  - ' + pub.year);
        if (pub.journal) lines.push('JO  - ' + pub.journal);
        if (pub.booktitle) lines.push('T2  - ' + pub.booktitle);
        if (pub.volume) lines.push('VL  - ' + pub.volume);
        if (pub.number) lines.push('IS  - ' + pub.number);
        if (pub.pages) {
            const p = pub.pages.split(/--|-/);
            if (p[0]) lines.push('SP  - ' + p[0].trim());
            if (p[1]) lines.push('EP  - ' + p[1].trim());
        }
        if (pub.publisher) lines.push('PB  - ' + pub.publisher);
        if (pub.school) lines.push('PB  - ' + pub.school);
        if (pub.doi) lines.push('DO  - ' + pub.doi);
        if (pub.url) lines.push('UR  - ' + pub.url);
        if (pub.abstract) lines.push('AB  - ' + pub.abstract);
        lines.push('ER  - ');
        return lines.join('\r\n');
    },

    getPublicationDateSortKey(pub) {
        const year = parseInt(pub.year) || 0;
        const monthMap = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        };
        let m = 0;
        if (pub.month) {
            const raw = pub.month.toLowerCase().replace(/[{}]/g, '').slice(0, 3);
            m = monthMap[raw] || 0;
        }
        return year * 100 + m;
    },

    calculateTotalAuthors(publications) {
        const unique = new Set();
        publications.forEach(pub => {
            if (pub.author) {
                const authors = this.parseAuthorList(pub.author);
                authors.forEach(a => {
                    const norm = (a.last + ' ' + (a.first ? a.first[0] : '')).toLowerCase().trim();
                    if (norm) unique.add(norm);
                });
            }
        });
        return unique.size;
    },

    // Theme Management
    getStoredTheme() {
        const stored = localStorage.getItem('slicer_ros2_theme');
        if (stored === 'dark' || stored === 'light') return stored;
        return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
    },

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('slicer_ros2_theme', theme);
        this.updateThemeToggleButtons(theme);
        window.dispatchEvent(new CustomEvent('theme-changed', { detail: { theme } }));
    },

    toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme') || this.getStoredTheme();
        const next = current === 'dark' ? 'light' : 'dark';
        this.setTheme(next);
    },

    updateThemeToggleButtons(theme) {
        document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
            const icon = btn.querySelector('.theme-toggle-icon');
            const text = btn.querySelector('.theme-toggle-text');
            if (theme === 'dark') {
                if (icon) icon.textContent = '☀️';
                if (text) text.textContent = 'Light';
                btn.setAttribute('title', 'Switch to light mode');
                btn.setAttribute('aria-label', 'Switch to light mode');
            } else {
                if (icon) icon.textContent = '🌙';
                if (text) text.textContent = 'Dark';
                btn.setAttribute('title', 'Switch to dark mode');
                btn.setAttribute('aria-label', 'Switch to dark mode');
            }
        });
    },

    initTheme() {
        const theme = this.getStoredTheme();
        document.documentElement.setAttribute('data-theme', theme);
        this.updateThemeToggleButtons(theme);

        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                if (!localStorage.getItem('slicer_ros2_theme')) {
                    this.setTheme(e.matches ? 'dark' : 'light');
                }
            });
        }

        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.theme-toggle-btn');
            if (btn) {
                e.preventDefault();
                this.toggleTheme();
            }
        });
    }
};

CONFIG.initTheme();
