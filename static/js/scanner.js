// QR Scanner and Product Lookup with Universal Multi-Device Support
let html5QrCode = null;
let isScannerRunning = false;
let availableCameras = [];
let currentCameraId = null;
let currentScannedProduct = null;

// Safe Toast notification caller
function notify(msg, type = 'info') {
    if (typeof showToast === 'function') {
        showToast(msg, type);
    } else {
        alert(msg);
    }
}

// Pleasant Audio Beep using Web Audio API
function playScanSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = "sine";
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 note
        gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.18);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.18);
    } catch (e) {
        console.log("Audio not supported or permitted:", e);
    }
}

// Function to sort and prioritize cameras (puts PC Camera and Webcams first, skips printers/scanners)
function prioritizeCameras(cameras) {
    if (!cameras || !cameras.length) return [];
    return [...cameras].sort((a, b) => {
        const labelA = (a.label || "").toLowerCase();
        const labelB = (b.label || "").toLowerCase();

        // Deprioritize non-cameras like Epson printer/scanner
        const isBadA = /epson|scanner|printer|virtual|fax/i.test(labelA);
        const isBadB = /epson|scanner|printer|virtual|fax/i.test(labelB);
        if (isBadA && !isBadB) return 1;
        if (!isBadA && isBadB) return -1;

        // Prioritize real webcams and USB cameras
        const isGoodA = /pc camera|webcam|camera|058f|usb|video/i.test(labelA);
        const isGoodB = /pc camera|webcam|camera|058f|usb|video/i.test(labelB);
        if (isGoodA && !isGoodB) return -1;
        if (!isGoodA && isGoodB) return 1;

        return 0;
    });
}

// Populate Camera Selector Dropdown
function updateCameraSelectDropdown(cameras) {
    const select = document.getElementById("cameraSelect");
    if (!select) return;

    if (!cameras || cameras.length === 0) {
        select.classList.add("hidden");
        return;
    }

    select.innerHTML = "";
    // Filter out obvious printers/scanners if real webcams exist
    const nonScanners = cameras.filter(c => !/epson|scanner|printer|fax|virtual/i.test(c.label || ""));
    const displayList = nonScanners.length > 0 ? nonScanners : cameras;

    displayList.forEach((cam, idx) => {
        const opt = document.createElement("option");
        opt.value = cam.id;
        let label = cam.label || `Kamera ${idx + 1}`;
        if (/epson|scanner|printer/i.test(label)) {
            label = `⚠️ ${label}`;
        } else if (/pc camera|058f/i.test(label)) {
            label = `📹 PC Camera (${cam.label || 'USB'})`;
        } else if (/back|rear|environment|orqa/i.test(label)) {
            label = `📷 Orqa Kamera`;
        } else if (/front|user|oldi|webcam/i.test(label)) {
            label = `🤳 Web Kamera`;
        }
        opt.text = label;
        if (currentCameraId === cam.id) {
            opt.selected = true;
        }
        select.appendChild(opt);
    });

    if (!currentCameraId && displayList.length > 0) {
        currentCameraId = displayList[0].id;
        select.value = currentCameraId;
    }

    if (displayList.length > 1) {
        select.classList.remove("hidden");
    } else {
        select.classList.add("hidden");
    }
}

// Start Camera Stream directly and safely
async function startCameraStream() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("MEDIA_DEVICES_NOT_SUPPORTED");
    }

    // Clean up any previous instance
    if (html5QrCode) {
        try { await html5QrCode.stop(); } catch (_) {}
        try { html5QrCode.clear(); } catch (_) {}
        html5QrCode = null;
    }

    const readerEl = document.getElementById("reader");
    if (readerEl) readerEl.innerHTML = "";

    // 1. Get available cameras
    let cameras = [];
    try {
        let rawCameras = await Html5Qrcode.getCameras();

        // If labels are empty (happens when permission not granted before getCameras),
        // run a quick getUserMedia to trigger permissions and populate real device labels
        if (!rawCameras || rawCameras.length === 0 || !rawCameras.some(c => c.label)) {
            try {
                const tempStream = await navigator.mediaDevices.getUserMedia({ video: true });
                tempStream.getTracks().forEach(t => t.stop());
                rawCameras = await Html5Qrcode.getCameras();
            } catch (permErr) {
                console.warn("Initial getUserMedia test error:", permErr);
            }
        }

        if (rawCameras && rawCameras.length > 0) {
            cameras = prioritizeCameras(rawCameras);
            availableCameras = cameras;
            updateCameraSelectDropdown(cameras);
        }
    } catch (camErr) {
        console.warn("getCameras xatosi:", camErr);
    }

    const scanConfig = {
        fps: 10,
        qrbox: function(viewfinderWidth, viewfinderHeight) {
            if (!viewfinderWidth || !viewfinderHeight || viewfinderWidth <= 0 || viewfinderHeight <= 0) {
                return { width: 220, height: 220 };
            }
            const minEdge = Math.min(viewfinderWidth, viewfinderHeight);
            const size = Math.max(120, Math.min(Math.floor(minEdge * 0.72), 240));
            return { width: size, height: size };
        }
    };

    // Helper to start an instance cleanly
    async function tryStart(cameraConfig) {
        if (html5QrCode) {
            try { await html5QrCode.stop(); } catch (_) {}
            try { html5QrCode.clear(); } catch (_) {}
            html5QrCode = null;
        }
        if (readerEl) readerEl.innerHTML = "";
        html5QrCode = new Html5Qrcode("reader");
        await html5QrCode.start(cameraConfig, scanConfig, onScanSuccess, onScanFailure);
    }

    let started = false;
    let lastErr = null;

    // Filter cameras to exclude printers/scanners (like Epson)
    const validCameras = cameras.filter(c => !/epson|scanner|printer|fax|virtual/i.test(c.label || ""));
    const cameraList = validCameras.length > 0 ? validCameras : cameras;

    // 2. Try starting with selected or prioritized cameras
    if (currentCameraId) {
        try {
            console.log("Tanlangan kamera ishga tushirilmoqda:", currentCameraId);
            await tryStart(currentCameraId);
            started = true;
        } catch (e) {
            console.warn("currentCameraId muvaffaqiyatsiz bo'ldi:", e);
            lastErr = e;
        }
    }

    if (!started && cameraList && cameraList.length > 0) {
        for (const cam of cameraList) {
            if (cam.id === currentCameraId) continue;
            try {
                console.log("Kamera ishga tushirilmoqda:", cam.label, cam.id);
                await tryStart(cam.id);
                currentCameraId = cam.id;
                const select = document.getElementById("cameraSelect");
                if (select) select.value = cam.id;
                started = true;
                break;
            } catch (e) {
                console.warn("Kamera ochilmadi, keyingisiga o'tamiz:", cam.label, e);
                lastErr = e;
            }
        }
    }

    // 3. Fallback: Generic constraints object (no ID, requests standard USB PC Camera)
    if (!started) {
        try {
            console.log("Fallback: generic constraints {} bilan urinilmoqda...");
            await tryStart({});
            started = true;
        } catch (e) {
            console.warn("Generic constraints {} ishlamadi:", e);
            lastErr = e;
        }
    }

    // 4. Fallback: try user facing camera
    if (!started) {
        try {
            console.log("Fallback: facingMode user bilan urinilmoqda...");
            await tryStart({ facingMode: "user" });
            started = true;
        } catch (e) {
            console.warn("facingMode user ishlamadi:", e);
            lastErr = e;
        }
    }

    // 5. Fallback: try environment facing camera
    if (!started) {
        try {
            console.log("Fallback: facingMode environment bilan urinilmoqda...");
            await tryStart({ facingMode: "environment" });
            started = true;
        } catch (e) {
            console.warn("facingMode environment ishlamadi:", e);
            lastErr = e;
        }
    }

    if (!started) {
        if (lastErr) throw lastErr;
        throw new Error("Kamera topilmadi yoki ochilmadi");
    }
}

// Toggle Live Camera on/off
async function toggleCamera() {
    const btn = document.getElementById("toggleScannerBtn");
    const btnText = document.getElementById("scannerBtnText");
    const placeholder = document.getElementById("cameraPlaceholder");
    const laserLine = document.getElementById("laserLine");
    const container = document.getElementById("reader-container");

    if (isScannerRunning) {
        if (html5QrCode) {
            try {
                await html5QrCode.stop();
                html5QrCode.clear();
            } catch (e) {
                console.log("Kamerani to'xtatishda xato:", e);
            }
            html5QrCode = null;
        }
        isScannerRunning = false;
        if (btnText) btnText.innerText = "Kamerani Yoqish";
        if (btn) {
            btn.classList.replace("bg-rose-600", "bg-sky-600");
            btn.classList.replace("hover:bg-rose-500", "hover:bg-sky-500");
        }
        if (placeholder) placeholder.classList.remove("hidden");
        if (laserLine) laserLine.classList.add("hidden");
        if (container) {
            container.classList.remove("min-h-[260px]");
            container.classList.add("min-h-[145px]");
        }
        notify("Kamera o'chirildi", "info");
    } else {
        try {
            if (placeholder) placeholder.classList.add("hidden");
            if (laserLine) laserLine.classList.remove("hidden");
            if (container) {
                container.classList.remove("min-h-[145px]");
                container.classList.add("min-h-[260px]");
            }

            await startCameraStream();
            isScannerRunning = true;
            if (btnText) btnText.innerText = "Kamerani O'chirish";
            if (btn) {
                btn.classList.replace("bg-sky-600", "bg-rose-600");
                btn.classList.replace("hover:bg-sky-500", "hover:bg-rose-500");
            }
            notify("Kamera yoqildi. Kafel QR kodini kameraga yaqinlashtiring", "success");
        } catch (err) {
            console.error("Kamerani ochishda xato:", err);
            
            if (html5QrCode) {
                try { await html5QrCode.stop(); } catch (_) {}
                try { html5QrCode.clear(); } catch (_) {}
                html5QrCode = null;
            }

            if (placeholder) placeholder.classList.remove("hidden");
            if (laserLine) laserLine.classList.add("hidden");
            if (container) {
                container.classList.remove("min-h-[260px]");
                container.classList.add("min-h-[145px]");
            }
            isScannerRunning = false;
            if (btnText) btnText.innerText = "Kamerani Yoqish";
            if (btn) {
                btn.classList.replace("bg-rose-600", "bg-sky-600");
                btn.classList.replace("hover:bg-rose-500", "hover:bg-sky-500");
            }

            const errStr = (typeof err === "string" ? err : (err.message || err.name || String(err))).toLowerCase();

            if (errStr.includes("notreadable") || errStr.includes("trackstart") || errStr.includes("could not start video source")) {
                notify("⚠️ Kamera band! Agar brauzer yuqorisida kamera oynasi (preview) ochiq bo'lsa, uni yopib qayta bosing.", "warning");
            } else if (errStr.includes("notallowed") || errStr.includes("permission")) {
                notify("⚠️ Kameraga brauzer ruxsati berilmadi! Brauzer manzilidagi qulf belgisidan ruxsat bering.", "danger");
            } else if (errStr.includes("overconstrained")) {
                notify("⚠️ Kamera o'lchamlari mos kelmadi. Boshqa kamerani tanlang.", "warning");
            } else if (errStr.includes("notfound") || errStr.includes("devices_not_supported")) {
                notify("⚠️ Kamera topilmadi! USB kamera ulanganligini tekshiring.", "warning");
            } else {
                notify(`⚠️ Kamera ochilmadi: ${err.message || err}`, "danger");
            }
        }
    }
}

// Switch Camera on the fly
async function switchCamera(selectedCameraId) {
    if (!selectedCameraId) return;
    currentCameraId = selectedCameraId;
    if (isScannerRunning) {
        try {
            await startCameraStream();
            notify("Kamera almashtirildi", "info");
        } catch (e) {
            console.error("Kamerani almashtirishda xato:", e);
            notify("Kamerani almashtirib bo'lmadi", "warning");
        }
    }
}

// Scan QR Code from File / Native Camera Photo Capture
async function scanQrFromImageFile(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];

    try {
        notify("QR kod tahlil qilinmoqda...", "info");
        if (!html5QrCode) {
            html5QrCode = new Html5Qrcode("reader");
        }
        if (isScannerRunning) {
            await toggleCamera();
        }

        const decodedText = await html5QrCode.scanFile(file, true);
        playScanSound();
        lookupProduct(decodedText);
    } catch (err) {
        console.error("Rasm orqali QR o'qishda xato:", err);
        notify("Suratdan QR kod topilmadi. Iltimos, QR kodni yaqinroq va yorug'roq joyda suratga oling.", "warning");
    } finally {
        input.value = "";
    }
}

function onScanSuccess(decodedText, decodedResult) {
    playScanSound();
    lookupProduct(decodedText);
}

function onScanFailure(error) {
    // Continuous background video scanning frame noise
}

async function lookupProduct(code) {
    try {
        code = (code || "").trim();
        if (code.includes("/")) {
            code = code.split("/").pop().trim();
        }
        const res = await fetch(`/api/product/by-code/${encodeURIComponent(code)}`);
        const data = await res.json();
        
        if (data.success && data.product) {
            displayScannedProduct(data.product);
            notify(`✅ ${data.product.brand} - ${data.product.model_name} aniqlandi!`, 'success');
        } else {
            notify(data.message || "Ushbu QR kodli kafel topilmadi!", 'warning');
        }
    } catch (err) {
        console.error("Qidirishda xato:", err);
        notify("Server bilan aloqa o'rnatib bo'lmadi!", 'danger');
    }
}

function displayScannedProduct(product) {
    currentScannedProduct = product;
    const card = document.getElementById("scannedProductCard");
    
    document.getElementById("cardSku").innerText = product.sku;
    document.getElementById("cardBrand").innerText = product.brand;
    document.getElementById("cardModel").innerText = product.model_name;
    document.getElementById("cardSize").innerText = product.size;
    document.getElementById("cardRack").innerText = product.location_rack ? `Tokcha: ${product.location_rack}` : '';
    
    // Image
    const imgEl = document.getElementById("cardImage");
    if (product.image_path) {
        imgEl.src = product.image_path;
        imgEl.classList.remove("hidden");
    } else {
        imgEl.src = "/static/placeholder-tile.png";
    }

    // Stock
    const stockEl = document.getElementById("cardStock");
    const unitEl = document.getElementById("cardUnit");
    const boxStockEl = document.getElementById("cardBoxStock");

    stockEl.innerText = product.quantity_in_stock;
    unitEl.innerText = product.unit;

    if (product.quantity_in_stock <= 0) {
        stockEl.className = "text-2xl font-black text-rose-600";
        boxStockEl.innerText = "(Omborda qolmagan!)";
    } else {
        stockEl.className = "text-2xl font-black text-emerald-600";
        if (product.box_size_m2 > 0) {
            const boxes = (product.quantity_in_stock / product.box_size_m2).toFixed(1);
            boxStockEl.innerText = `(~${boxes} quti)`;
        } else {
            boxStockEl.innerText = "";
        }
    }

    // Price
    document.getElementById("cardPrice").innerText = Number(product.price).toLocaleString("ru-RU");
    document.getElementById("cardBoxSize").innerText = `${product.box_size_m2} m² (${product.pieces_per_box} dona)`;

    // Reset qty
    document.getElementById("addQtyInput").value = 1;

    card.classList.remove("hidden");
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function searchByManualCode() {
    const input = document.getElementById("manualCodeInput");
    const code = input.value.trim();
    if (!code) {
        notify("Iltimos, QR kod yoki SKU kiriting!", "warning");
        return;
    }
    lookupProduct(code);
}

// Enter key press in manual input and Auto-load camera list on page load
document.addEventListener("DOMContentLoaded", () => {
    const manualInput = document.getElementById("manualCodeInput");
    if (manualInput) {
        manualInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                searchByManualCode();
            }
        });
    }

    // Pre-query cameras if Html5Qrcode is available
    if (typeof Html5Qrcode !== "undefined" && navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        Html5Qrcode.getCameras().then(cameras => {
            if (cameras && cameras.length > 0) {
                const prioritized = prioritizeCameras(cameras);
                availableCameras = prioritized;
                updateCameraSelectDropdown(prioritized);
            }
        }).catch(err => {
            console.log("Kamerani oldindan aniqlashda:", err);
        });
    }
});
