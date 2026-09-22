// QR Scanner and Product Lookup
let html5QrCode = null;
let isScannerRunning = false;
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

async function toggleCamera() {
    const btn = document.getElementById("toggleScannerBtn");
    const btnText = document.getElementById("scannerBtnText");
    const placeholder = document.getElementById("cameraPlaceholder");
    const laserLine = document.getElementById("laserLine");
    const container = document.getElementById("reader-container");

    if (isScannerRunning) {
        if (html5QrCode) {
            await html5QrCode.stop();
            html5QrCode.clear();
        }
        isScannerRunning = false;
        btnText.innerText = "Kamerani Yoqish";
        btn.classList.replace("bg-rose-600", "bg-sky-600");
        btn.classList.replace("hover:bg-rose-500", "hover:bg-sky-500");
        placeholder.classList.remove("hidden");
        if (laserLine) laserLine.classList.add("hidden");
        if (container) {
            container.classList.remove("min-h-[260px]");
            container.classList.add("min-h-[145px]");
        }
        notify("Kamera o'chirildi", "info");
    } else {
        html5QrCode = new Html5Qrcode("reader");
        const config = {
            fps: 12,
            qrbox: { width: 240, height: 240 },
            aspectRatio: 1.0
        };

        try {
            placeholder.classList.add("hidden");
            if (laserLine) laserLine.classList.remove("hidden");
            if (container) {
                container.classList.remove("min-h-[145px]");
                container.classList.add("min-h-[260px]");
            }

            await html5QrCode.start(
                { facingMode: "environment" },
                config,
                onScanSuccess,
                onScanFailure
            );
            isScannerRunning = true;
            btnText.innerText = "Kamerani O'chirish";
            btn.classList.replace("bg-sky-600", "bg-rose-600");
            btn.classList.replace("hover:bg-sky-500", "hover:bg-rose-500");
            notify("Kamera yoqildi. QR kodni yaqinlashtiring", "info");
        } catch (err) {
            console.error("Kamerani ochishda xato:", err);
            placeholder.classList.remove("hidden");
            if (laserLine) laserLine.classList.add("hidden");
            if (container) {
                container.classList.remove("min-h-[260px]");
                container.classList.add("min-h-[145px]");
            }
            notify("Kamerani yoqish imkoni bo'lmadi! Ruxsat bering yoki SKU qidiruvidan foydalaning.", "danger");
        }
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

// Enter key press in manual input
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
});
