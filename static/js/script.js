document.addEventListener('DOMContentLoaded', () => {
    // ===== Theme Toggle =====
    const themeToggle = document.getElementById('theme-toggle');
    const iconSun = document.getElementById('icon-sun');
    const iconMoon = document.getElementById('icon-moon');

    function applyTheme(dark) {
        if (dark) {
            document.documentElement.classList.add('dark');
            iconSun.classList.remove('icon-hidden');
            iconMoon.classList.add('icon-hidden');
        } else {
            document.documentElement.classList.remove('dark');
            iconMoon.classList.remove('icon-hidden');
            iconSun.classList.add('icon-hidden');
        }
    }

    const savedTheme = localStorage.getItem('color-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(savedTheme === 'dark' || (!savedTheme && prefersDark));

    themeToggle.addEventListener('click', () => {
        const isDark = document.documentElement.classList.contains('dark');
        applyTheme(!isDark);
        localStorage.setItem('color-theme', isDark ? 'light' : 'dark');
    });

    // ===== Toast =====
    const toastEl = document.getElementById('toast');
    let toastTimeout;
    function showToast(message, duration = 2500) {
        clearTimeout(toastTimeout);
        toastEl.textContent = message;
        toastEl.classList.add('show');
        toastTimeout = setTimeout(() => toastEl.classList.remove('show'), duration);
    }

    // ===== DOM Elements =====
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadCard = document.getElementById('upload-card');
    const resultCard = document.getElementById('result-card');
    const uploadSpinner = document.getElementById('upload-spinner');
    const uploadEffects = document.getElementById('upload-effects');
    const filterButtons = document.getElementById('filter-buttons');
    const gallery = document.getElementById('gallery');
    const mainScannedImage = document.getElementById('main-scanned-image');
    const downloadImageBtn = document.getElementById('download-image-btn');
    const scanAgainBtn = document.getElementById('scan-again-btn');
    const effectBadgeText = document.getElementById('effect-badge-text');

    let scannedImagePath = '';
    let originalImagePath = '';
    let currentEffect = 'original';
    let imagesByEffect = {};
    let availableEffects = [];

    const EFFECT_LABELS = {
        original: 'Original',
        rgb: 'RGB',
        low_contrast: 'Low Contrast',
        high_contrast: 'High Contrast',
        median: 'Median Blur',
        average: 'Average Blur',
        black_white: 'Black & White',
    };
    const DEFAULT_EFFECTS = ['original', 'rgb', 'low_contrast', 'high_contrast', 'median', 'average', 'black_white'];

    function labelFor(effect) {
        return EFFECT_LABELS[effect] || effect;
    }

    function setActiveButton(container, effect) {
        container.querySelectorAll('.effect-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.effect === effect);
        });
    }

    function buildButtons(container, effects, onSelect) {
        container.innerHTML = '';
        effects.forEach(effect => {
            const btn = document.createElement('button');
            btn.className = 'effect-btn';
            btn.dataset.effect = effect;
            btn.textContent = labelFor(effect);
            btn.addEventListener('click', () => onSelect(effect));
            container.appendChild(btn);
        });
    }

    function updateEffectBadge() {
        effectBadgeText.textContent = labelFor(currentEffect);
    }

    function updateDownloadLink() {
        const url = imagesByEffect[currentEffect];
        if (!url) return;
        const ext = (url.split('.').pop() || 'png').split('?')[0];
        const safe = currentEffect.replace(/[^a-z0-9]+/gi, '_').toLowerCase();
        downloadImageBtn.href = url;
        downloadImageBtn.download = `scan_${safe}.${ext}`;
    }

    function buildGallery(effects, images) {
        gallery.innerHTML = '';
        effects.forEach(effect => {
            const item = document.createElement('div');
            item.className = 'gallery-item';
            item.dataset.effect = effect;

            const img = document.createElement('img');
            img.src = images[effect];
            img.alt = labelFor(effect);

            const label = document.createElement('div');
            label.className = 'gallery-label';
            label.textContent = labelFor(effect);

            item.appendChild(img);
            item.appendChild(label);
            item.addEventListener('click', () => setActiveEffect(effect));
            gallery.appendChild(item);
        });
    }

    function setActiveEffect(effect) {
        if (!imagesByEffect[effect]) return;
        currentEffect = effect;
        scannedImagePath = imagesByEffect[effect];
        
        if (mainScannedImage) {
            mainScannedImage.src = scannedImagePath;
        }

        updateEffectBadge();
        updateDownloadLink();
        setActiveButton(filterButtons, effect);
        gallery.querySelectorAll('.gallery-item').forEach(item => {
            item.classList.toggle('active', item.dataset.effect === effect);
        });
    }

    buildButtons(uploadEffects, DEFAULT_EFFECTS, effect => {
        currentEffect = effect;
        setActiveButton(uploadEffects, effect);
    });
    setActiveButton(uploadEffects, currentEffect);

    // ===== File Upload =====
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFiles(e.target.files));

    // Drag & Drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false);
    });
    ['dragenter', 'dragover'].forEach(evt => {
        dropZone.addEventListener(evt, () => dropZone.classList.add('dragging', 'pulse'), false);
    });
    ['dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, () => dropZone.classList.remove('dragging', 'pulse'), false);
    });
    dropZone.addEventListener('drop', (e) => handleFiles(e.dataTransfer.files), false);

    // Paste
    const imageExtensionPattern = /\.(png|jpe?g|gif|bmp|webp|tiff?)$/i;
    function isLikelyImage(file) {
        if (!file) return false;
        if (file.type && file.type.startsWith('image/')) return true;
        return Boolean(file.name && imageExtensionPattern.test(file.name));
    }

    document.addEventListener('paste', (e) => {
        const cd = e.clipboardData;
        if (!cd) return;
        let images = [];
        if (cd.files && cd.files.length) {
            images = Array.from(cd.files).filter(isLikelyImage);
        } else if (cd.items) {
            images = Array.from(cd.items)
                .filter(item => item.kind === 'file')
                .map(item => item.getAsFile())
                .filter(isLikelyImage);
        }
        if (images.length) {
            e.preventDefault();
            handleFiles(images);
        }
    });

    async function handleFiles(files) {
        const file = files[0];
        if (!isLikelyImage(file)) {
            showToast('Please upload an image file');
            return;
        }

        uploadSpinner.classList.add('visible');
        dropZone.style.display = 'none';

        const formData = new FormData();
        formData.append('file', file);
        formData.append('effect', currentEffect);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                let msg = 'Upload failed';
                try {
                    const errData = await response.json();
                    msg = errData.detail || errData.message || msg;
                } catch {}
                throw new Error(msg);
            }

            const result = await response.json();
            originalImagePath = result.original_image_url;
            const filterList = Array.isArray(result.filters) ? result.filters : DEFAULT_EFFECTS.slice(1);
            availableEffects = ['original', ...filterList];
            imagesByEffect = { original: originalImagePath, ...(result.filtered_images || {}) };

            buildButtons(filterButtons, availableEffects, setActiveEffect);
            buildGallery(availableEffects, imagesByEffect);

            const preferred = availableEffects.includes(result.selected_effect) ? result.selected_effect : 'original';
            setActiveEffect(preferred);

            // Transition: upload → result
            uploadCard.classList.add('zoom-out');
            uploadCard.addEventListener('animationend', function handler() {
                uploadCard.removeEventListener('animationend', handler);
                uploadCard.style.display = 'none';
                uploadCard.classList.remove('zoom-out');
                resultCard.classList.add('visible', 'zoom-in');
            });

        } catch (error) {
            console.error('Upload error:', error);
            showToast(error.message || 'Upload failed');
            uploadSpinner.classList.remove('visible');
            dropZone.style.display = '';
        }
    }

    // ===== Scan Again =====
    scanAgainBtn.addEventListener('click', () => {
        resultCard.classList.add('zoom-out');
        resultCard.addEventListener('animationend', function handler() {
            resultCard.removeEventListener('animationend', handler);
            resultCard.classList.remove('visible', 'zoom-in', 'zoom-out');

            // Reset upload card
            uploadSpinner.classList.remove('visible');
            dropZone.style.display = '';
            uploadCard.style.display = '';
            uploadCard.classList.add('zoom-in');
            fileInput.value = '';
        });
    });
});
