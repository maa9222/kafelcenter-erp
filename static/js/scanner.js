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

// Populate Camera Selector Dropdown
function updateCameraSelectDropdown(cameras) {
    const select = document.getElementById("cameraSelect");
    if (!select) return;

    if (!cameras || cameras.length <= 1) {
        select.classList.add("hidden");
        return;
    }

    select.innerHTML = "";
    cameras.forEach((cam, idx) => {
        const opt = document.createElement("option");
        opt.value = cam.id;
        let label = cam.label || `Kamera ${idx + 1}`;
        if (/back|rear|environment|orqa/i.test(label)) {
            label = "📷 Orqa Kamera";
        } else if (/front|user|oldi|webcam/i.test(label)) {
            label = "🤳 Oldi Kamera";
        }
        opt.text = label;
        if (currentCameraId === cam.id) {
            opt.selected = true;
        }
        select.appendChild(opt);
    });
    select.classList.remove("hidden");
}

// Modal handlers for camera permission guide
function showCameraPermissionModal() {
    const m = document.getElementById("cameraPermissionModal");
    if (m) {
        m.classList.remove("hidden");
        m.classList.add("flex");
    }
}

function closeCameraPermissionModal() {
    const m = document.getElementById("cameraPermissionModal");
    if (m) {
        m.classList.add("hidden");
        m.classList.remove("flex");
    }
}

// Multi-Level Camera Startup Strategy without breaking constraints
async function startCameraStream() {
    // 1. Check if mediaDevices is supported (requires secure context or localhost)
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        const isSecure = window.isSecureContext || location.hostname === "localhost" || location.hostname === "127.0.0.1";
        if (!isSecure) {
            throw new Error("SECURE_CONTEXT_REQUIRED");
        }
        throw new Error("MEDIA_DEVICES_NOT_SUPPORTED");
    }

    // 2. Request camera stream directly with plain video constraint (triggers browser permission popup)
    try {
        const testStream = await navigator.mediaDevices.getUserMedia({ video: true });
        // Permission successfully obtained! Release test tracks so camera is available for scanner:
        testStream.getTracks().forEach(track => track.stop());
    } catch (permErr) {
        console.error("Kameraga ruxsat tekshiruvida xato:", permErr);
        throw permErr;
    }

    // Clean up any old instance
    if (html5QrCode) {
        try { await html5QrCode.stop(); } catch (_) {}
        try { html5QrCode.clear(); } catch (_) {}
        html5QrCode = null;
    }
    html5QrCode = new Html5Qrcode("reader");

    // Minimal, standard scan config - NO aspectRatio, NO torch constraints that crash USB webcams
    const config = {
        fps: 10,
        qrbox: function(viewfinderWidth, viewfinderHeight) {
            const minEdge = Math.min(viewfinderWidth, viewfinderHeight);
            const size = Math.max(120, Math.min(Math.floor(minEdge * 0.72), 240));
            return { width: size, height: size };
        }
    };

    // 3. Enumerate cameras now that permission is granted
    try {
        availableCameras = await Html5Qrcode.getCameras();
        updateCameraSelectDropdown(availableCameras);
    } catch (camErr) {
        console.warn("Kamerlar ro'yxatini olib bo'lmadi:", camErr);
    }

    // 4. Attempt: specific selected camera ID
    if (currentCameraId) {
        try {
            await html5QrCode.start(currentCameraId, config, onScanSuccess, onScanFailure);
            return;
        } catch (e) {
            console.warn("Tanlangan camera ID ishlamadi, fallback sinoviga o'tamiz:", e);
        }
    }

    // 5. Attempt: first available camera from getCameras
    if (availableCameras && availableCameras.length > 0) {
        const backCam = availableCameras.find(c => /back|rear|environment|orqa/i.test(c.label));
        const candidate = backCam || availableCameras[0];
        try {
            currentCameraId = candidate.id;
            const select = document.getElementById("cameraSelect");
            if (select) select.value = candidate.id;
            await html5QrCode.start(candidate.id, config, onScanSuccess, onScanFailure);
            return;
        } catch (e) {
            console.warn("Candidate camera ID ishlamadi, constraints bilan sinaymiz:", e);
        }
    }

    // 6. Attempt: facingMode user (Webcam / Laptop camera)
    try {
        await html5QrCode.start({ facingMode: "user" }, config, onScanSuccess, onScanFailure);
        return;
    } catch (e) {
        console.warn("facingMode: user ishlamadi:", e);
    }

    // 7. Attempt: facingMode environment (Back camera)
    try {
        await html5QrCode.start({ facingMode: "environment" }, config, onScanSuccess, onScanFailure);
        return;
    } catch (e) {
        console.warn("facingMode: environment ishlamadi:", e);
    }

    // 8. Attempt: default video track (true)
    await html5QrCode.start(true, config, onScanSuccess, onScanFailure);
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
            notify("Kamera yoqildi. QR kodni yaqinlashtiring", "info");
        } catch (err) {
            console.error("Kamerani ochishda xato:", err);
            
            // Clean up html5QrCode so next attempt starts clean
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

            // Accurate, friendly error diagnosis
            const errName = err.name || "";
            const errStr = (typeof err === "string" ? err : (err.message || err.name || String(err))).toLowerCase();

            if (errStr.includes("secure_context_required")) {
                notify("⚠️ Brauzer xavfsizlik talabi: Jonli kamera faqat HTTPS yoki localhost (127.0.0.1) orqali ishlaydi. 'Rasm / Surat' tugmasidan foydalaning!", "warning");
            } else if (errName === "NotAllowedError" || errStr.includes("notallowed") || errStr.includes("permission") || errStr.includes("denied")) {
                showCameraPermissionModal();
                notify("⚠️ Kameraga brauzer ruxsati berilmagan! Ekrandagi ko'rsatmaga qarang yoki 'Rasm / Surat' tugmasini bosing.", "danger");
            } else if (errName === "NotFoundError" || errName === "DevicesNotFoundError" || errStr.includes("not found") || errStr.includes("notfound")) {
                notify("⚠️ Kompyuterda kamera topilmadi! 'Rasm / Surat' tugmasi orqali rasm yuklang yoki SKU qidiruvidan foydalaning.", "warning");
            } else if (errName === "NotReadableError" || errName === "TrackStartError" || errStr.includes("in use") || errStr.includes("notreadable")) {
                notify("⚠️ Kamera boshqa dastur tomonidan band qilingan. Uni yopib qayta urinib ko'ring.", "warning");
            } else {
                notify(`⚠️ Kamera xatosi: ${err.message || err.name || err}. 'Rasm / Surat' tugmasidan foydalanishingiz mumkin.`, "danger");
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
            await html5QrCode.stop();
            const config = {
                fps: 10,
                qrbox: function(viewfinderWidth, viewfinderHeight) {
                    const minEdge = Math.min(viewfinderWidth, viewfinderHeight);
                    const size = Math.max(120, Math.min(Math.floor(minEdge * 0.72), 240));
                    return { width: size, height: size };
                }
            };
            await html5QrCode.start(currentCameraId, config, onScanSuccess, onScanFailure);
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
                availableCameras = cameras;
                updateCameraSelectDropdown(cameras);
            }
        }).catch(err => {
            console.log("Kamerani oldindan aniqlashda:", err);
        });
    }
});
