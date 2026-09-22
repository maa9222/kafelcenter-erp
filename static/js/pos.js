// Cart (Savat) & POS Logic with Multi-Cart (Hold Cart) Support
let currentCartTab = 1;
const CART_STORAGE_KEY = "kafel_pos_cart";
let activeCalcProduct = null;
let currentDiscountAmount = 0;

// Safe notification helper
function posNotify(msg, type = 'info') {
    if (typeof showToast === 'function') {
        showToast(msg, type);
    } else {
        alert(msg);
    }
}

function getCartStorageKey(tab = currentCartTab) {
    return tab === 1 ? CART_STORAGE_KEY : `${CART_STORAGE_KEY}_${tab}`;
}

function getCart(tab = currentCartTab) {
    try {
        const key = getCartStorageKey(tab);
        const data = localStorage.getItem(key);
        return data ? JSON.parse(data) : [];
    } catch (e) {
        return [];
    }
}

function saveCart(cart, tab = currentCartTab) {
    localStorage.setItem(getCartStorageKey(tab), JSON.stringify(cart));
    updateCartUI();
}

function switchCartTab(tab) {
    currentCartTab = tab;
    const btn1 = document.getElementById("cartTabBtn1");
    const btn2 = document.getElementById("cartTabBtn2");
    const titleEl = document.getElementById("cartActiveTitle");

    if (btn1 && btn2) {
        if (tab === 1) {
            btn1.className = "flex-1 py-1.5 px-3 rounded-lg bg-white text-slate-900 shadow-2xs transition flex items-center justify-center space-x-1.5 font-bold";
            btn2.className = "flex-1 py-1.5 px-3 rounded-lg text-slate-500 hover:text-slate-800 transition flex items-center justify-center space-x-1.5 font-medium";
            if (titleEl) titleEl.innerText = "Savat #1 dagi Kafellar";
        } else {
            btn2.className = "flex-1 py-1.5 px-3 rounded-lg bg-white text-slate-900 shadow-2xs transition flex items-center justify-center space-x-1.5 font-bold";
            btn1.className = "flex-1 py-1.5 px-3 rounded-lg text-slate-500 hover:text-slate-800 transition flex items-center justify-center space-x-1.5 font-medium";
            if (titleEl) titleEl.innerText = "Savat #2 (Kutishdagi Savat)";
        }
    }
    updateCartUI();
    posNotify(`Savat #${tab} ga o'tildi`, "info");
}

function clearCart() {
    const doClear = () => {
        localStorage.removeItem(getCartStorageKey(currentCartTab));
        updateCartUI();
        if (typeof renderKassaPage === "function") {
            renderKassaPage();
        }
        posNotify(`Savat #${currentCartTab} tozalandi`, "info");
    };

    if (typeof showConfirmModal === "function") {
        showConfirmModal({
            title: "Savatni tozalash",
            message: "Rostdan ham tanlangan barcha kafellarni ro'yxatdan o'chirmoqchimisiz?",
            icon: "fa-solid fa-trash-can text-rose-500",
            confirmText: "Ha, Tozalash",
            confirmClass: "px-5 py-2.5 rounded-xl text-xs font-black bg-rose-600 hover:bg-rose-500 text-white shadow-md transition",
            onConfirm: doClear
        });
    } else {
        if (confirm("Rostdan ham tanlangan kafellar ro'yxatini tozalamoqchimisiz?")) {
            doClear();
        }
    }
}

function addScannedProductToCart() {
    if (!currentScannedProduct) return;

    const qtyInput = document.getElementById("addQtyInput");
    const qty = parseFloat(qtyInput.value) || 1;

    if (qty <= 0) {
        posNotify("Iltimos, musbat miqdor kiriting!", "warning");
        return;
    }

    if (qty > currentScannedProduct.quantity_in_stock) {
        posNotify(`Omborda faqat ${currentScannedProduct.quantity_in_stock} ${currentScannedProduct.unit} mavjud!`, "danger");
        return;
    }

    addProductToCartData(currentScannedProduct, qty);
}

function addProductToCartData(product, qty) {
    const cart = getCart();
    const isDefect = product.is_defect ? 1 : 0;
    const defectId = product.defect_id || null;
    const maxStock = isDefect ? (product.quantity !== undefined ? product.quantity : product.stock) : (product.quantity_in_stock !== undefined ? product.quantity_in_stock : product.stock);

    const existingIndex = cart.findIndex(item => {
        if (isDefect) {
            return item.is_defect === 1 && item.defect_id === defectId;
        }
        return (!item.is_defect || item.is_defect === 0) && item.id === product.id;
    });

    if (existingIndex > -1) {
        const newTotalQty = Math.round((cart[existingIndex].qty + qty) * 100) / 100;
        if (newTotalQty > maxStock) {
            posNotify(`Mavjud qoldiq: ${maxStock} ${product.unit}. Savatda allaqachon ${cart[existingIndex].qty} mavjud.`, "warning");
            return;
        }
        cart[existingIndex].qty = newTotalQty;
    } else {
        cart.push({
            id: product.product_id || product.id,
            sku: product.sku || (isDefect ? `BRAK-${defectId}` : ''),
            brand: product.brand,
            model_name: product.model_name,
            size: product.size,
            unit: product.unit,
            price: Number(product.discounted_price || product.price),
            stock: maxStock,
            box_size_m2: product.box_size_m2 || 1.44,
            image_path: product.image_path,
            qty: Math.round(qty * 100) / 100,
            is_defect: isDefect,
            defect_id: defectId
        });
    }

    saveCart(cart);
    posNotify(`✅ ${product.brand} - ${product.model_name} (${qty} ${product.unit}) savatga qo'shildi!`, "success");
}

function updateCartItemByIndex(index, delta) {
    const cart = getCart();
    if (!cart[index]) return;
    const item = cart[index];
    const newQty = Math.round((item.qty + delta) * 10) / 10;
    if (newQty <= 0) {
        removeCartItemByIndex(index);
        return;
    }
    if (newQty > item.stock) {
        posNotify(`Mavjud qoldiq faqat ${item.stock} ${item.unit}!`, "warning");
        return;
    }
    item.qty = newQty;
    saveCart(cart);
    if (typeof renderKassaPage === "function") {
        renderKassaPage();
    }
}

function removeCartItemByIndex(index) {
    let cart = getCart();
    if (!cart[index]) return;
    cart.splice(index, 1);
    saveCart(cart);
    if (typeof renderKassaPage === "function") {
        renderKassaPage();
    }
    posNotify("Mahsulot savatdan olib tashlandi", "info");
}

function updateItemQty(productId, delta) {
    const cart = getCart();
    const index = cart.findIndex(i => i.id === productId);
    if (index > -1) {
        updateCartItemByIndex(index, delta);
    }
}

function removeFromCart(productId) {
    const cart = getCart();
    const index = cart.findIndex(i => i.id === productId);
    if (index > -1) {
        removeCartItemByIndex(index);
    }
}

function updateCartUI() {
    const cart = getCart();

    // Update nav badge if present
    const badge = document.getElementById("cartCountBadge");
    if (badge) {
        badge.innerText = cart.length;
    }

    // Update Hold Cart Tab Badges
    const badge1 = document.getElementById("cartCountBadge1");
    const badge2 = document.getElementById("cartCountBadge2");
    if (badge1) badge1.innerText = getCart(1).length;
    if (badge2) badge2.innerText = getCart(2).length;

    const itemsContainer = document.getElementById("cartItemsList");
    const emptyMsg = document.getElementById("emptyCartMessage");
    const totalItemsEl = document.getElementById("cartTotalItems");
    const totalAreaEl = document.getElementById("cartTotalArea");
    const totalSumEl = document.getElementById("cartTotalSum");
    const checkoutBtn = document.getElementById("checkoutBtn");
    const auxBox = document.getElementById("cartAuxBox");
    const auxKley = document.getElementById("auxKleyVal");
    const auxZat = document.getElementById("auxZatirkaVal");
    const auxSvp = document.getElementById("auxSvpVal");

    if (!itemsContainer) return; // Not on sales page

    if (cart.length === 0) {
        itemsContainer.innerHTML = "";
        if (emptyMsg) itemsContainer.appendChild(emptyMsg);
        if (totalItemsEl) totalItemsEl.innerText = "0 xil";
        if (totalAreaEl) totalAreaEl.innerText = "0 m²";
        if (totalSumEl) totalSumEl.innerText = "0";
        if (auxBox) auxBox.classList.add("hidden");
        if (checkoutBtn) {
            checkoutBtn.classList.add("pointer-events-none", "opacity-50");
        }
        return;
    }

    if (checkoutBtn) {
        checkoutBtn.classList.remove("pointer-events-none", "opacity-50");
    }

    let html = "";
    let totalArea = 0;
    let totalSum = 0;

    cart.forEach((item, index) => {
        const itemSum = item.qty * item.price;
        totalArea += item.qty;
        totalSum += itemSum;
        const boxCount = item.box_size_m2 > 0 ? (item.qty / item.box_size_m2).toFixed(1) : "-";

        html += `
        <div class="p-2.5 rounded-xl ${item.is_defect ? 'bg-rose-50/60 border border-rose-200' : 'bg-slate-50/80 border border-slate-200'} flex items-center justify-between gap-2.5 hover:border-slate-300 transition shadow-2xs">
            <div class="flex items-center space-x-2.5 overflow-hidden min-w-0">
                <div class="w-11 h-11 rounded-lg bg-white overflow-hidden border border-slate-200 flex-shrink-0 relative flex items-center justify-center p-0.5 shadow-2xs cursor-pointer" onclick="openTileImageModal('${item.image_path || '/static/placeholder-tile.png'}')">
                    <img src="${item.image_path || '/static/placeholder-tile.png'}" class="max-h-full max-w-full object-contain rounded">
                    ${item.is_defect ? '<span class="absolute bottom-0 inset-x-0 bg-rose-600 text-white text-[7px] font-black text-center uppercase">Brak</span>' : ''}
                </div>
                <div class="overflow-hidden min-w-0">
                    <div class="flex items-center space-x-1">
                        <span class="text-[9px] font-black uppercase text-sky-600 tracking-wider truncate">${item.brand}</span>
                        ${item.is_defect ? '<span class="text-[8px] font-bold uppercase bg-rose-100 text-rose-700 px-1 rounded">Siniq</span>' : ''}
                    </div>
                    <h4 class="font-bold text-xs text-slate-800 truncate">${item.model_name}</h4>
                    <div class="text-[10px] text-slate-500 font-medium flex items-center space-x-1.5 truncate">
                        <span>${item.size}</span>
                        <span>&bull;</span>
                        <b class="${item.is_defect ? 'text-rose-700 font-black' : 'text-slate-800 font-bold'}">${Number(item.price).toLocaleString('ru-RU')} s.</b>
                        <span>&bull;</span>
                        <span class="text-sky-600 font-bold">~${boxCount} quti</span>
                    </div>
                </div>
            </div>

            <div class="flex items-center space-x-1.5 flex-shrink-0">
                <div class="flex items-center bg-white border border-slate-200 rounded-lg p-0.5 shadow-2xs">
                    <button onclick="updateCartItemByIndex(${index}, -1)" class="w-5 h-5 rounded text-slate-600 hover:bg-slate-100 flex items-center justify-center font-bold text-xs transition">-</button>
                    <span class="px-1.5 font-mono font-bold text-xs text-slate-900">${item.qty}</span>
                    <button onclick="updateCartItemByIndex(${index}, 1)" class="w-5 h-5 rounded text-slate-600 hover:bg-slate-100 flex items-center justify-center font-bold text-xs transition">+</button>
                </div>
                <button onclick="removeCartItemByIndex(${index})" class="text-slate-400 hover:text-rose-600 p-1 transition" title="O'chirish">
                    <i class="fa-solid fa-xmark text-xs"></i>
                </button>
            </div>
        </div>
        `;
    });

    itemsContainer.innerHTML = html;
    if (totalItemsEl) totalItemsEl.innerText = `${cart.length} xil`;
    if (totalAreaEl) totalAreaEl.innerText = `${Math.round(totalArea * 10) / 10} m²`;
    if (totalSumEl) totalSumEl.innerText = Number(totalSum).toLocaleString("ru-RU");

    // Auto-calculate auxiliary materials for the showroom
    if (auxBox && totalArea > 0) {
        auxBox.classList.remove("hidden");
        const kley = Math.ceil(totalArea / 5);
        const zat = Math.ceil(totalArea * 0.4);
        const svp = Math.ceil(totalArea * 30);
        if (auxKley) auxKley.innerText = `${kley} qop`;
        if (auxZat) auxZat.innerText = `${zat} kg`;
        if (auxSvp) auxSvp.innerText = `${svp} dona`;
    } else if (auxBox) {
        auxBox.classList.add("hidden");
    }
}

// ---------------- SMART TILE & ROOM CALCULATOR ----------------

function openTileCalculator(product = null) {
    const modal = document.getElementById("tileCalcModal");
    if (!modal) return;

    activeCalcProduct = product || currentScannedProduct;
    const titleEl = document.getElementById("calcTileTitle");
    const sizeEl = document.getElementById("calcTileSize");
    const boxEl = document.getElementById("calcTileBox");

    if (activeCalcProduct) {
        if (titleEl) titleEl.innerText = `${activeCalcProduct.brand} - ${activeCalcProduct.model_name}`;
        if (sizeEl) sizeEl.innerText = `O'lcham: ${activeCalcProduct.size}`;
        if (boxEl) boxEl.innerText = `1 Quti: ${activeCalcProduct.box_size_m2 || 1.44} m²`;
    } else {
        if (titleEl) titleEl.innerText = "Umumiy Kafel Hisoblagich";
        if (sizeEl) sizeEl.innerText = "O'lcham: 60x120 yoki tanlangan";
        if (boxEl) boxEl.innerText = "1 Quti: 1.44 m²";
    }

    modal.classList.remove("hidden");
    calculateTileRequirement();
}

function closeTileCalculator() {
    const modal = document.getElementById("tileCalcModal");
    if (modal) modal.classList.add("hidden");
}

function calculateTileRequirement() {
    const calcType = document.querySelector('input[name="calcType"]:checked')?.value || "pol";
    const length = parseFloat(document.getElementById("calcLength")?.value) || 0;
    const width = parseFloat(document.getElementById("calcWidth")?.value) || 0;
    const height = parseFloat(document.getElementById("calcHeight")?.value) || 0;
    const minusArea = parseFloat(document.getElementById("calcMinusArea")?.value) || 0;
    const wastePercent = parseFloat(document.getElementById("calcWaste")?.value) || 10;

    let baseArea = 0;
    if (calcType === "pol") {
        baseArea = length * width;
    } else {
        // Devor: perimetr * balandlik - eshik/deraza
        baseArea = Math.max(0, (2 * (length + width) * height) - minusArea);
    }

    const withWasteArea = baseArea * (1 + (wastePercent / 100));
    const boxSize = activeCalcProduct?.box_size_m2 || 1.44;
    const neededBoxes = boxSize > 0 ? Math.ceil(withWasteArea / boxSize) : 0;
    const finalArea = Math.round(neededBoxes * boxSize * 100) / 100;
    const tilePrice = activeCalcProduct?.price || 150000;
    const totalCost = finalArea * tilePrice;

    // Render results
    const netAreaEl = document.getElementById("calcNetArea");
    const boxesEl = document.getElementById("calcBoxesCount");
    const finalAreaEl = document.getElementById("calcFinalArea");
    const totalCostEl = document.getElementById("calcTotalCost");

    if (netAreaEl) netAreaEl.innerText = `${baseArea.toFixed(2)} m²`;
    if (boxesEl) boxesEl.innerText = `${neededBoxes} quti`;
    if (finalAreaEl) finalAreaEl.innerText = `${finalArea.toFixed(2)} m²`;
    if (totalCostEl) totalCostEl.innerText = `${Number(totalCost).toLocaleString('ru-RU')} so'm`;

    return { finalArea, neededBoxes, totalCost };
}

function applyCalculatorResult() {
    const res = calculateTileRequirement();
    if (res.finalArea <= 0) {
        posNotify("Iltimos, xona o'lchamlarini to'g'ri kiriting!", "warning");
        return;
    }

    if (!activeCalcProduct && currentScannedProduct) {
        activeCalcProduct = currentScannedProduct;
    }

    if (activeCalcProduct) {
        addProductToCartData(activeCalcProduct, res.finalArea);
        closeTileCalculator();
    } else {
        // Just set the manual qty
        const addQty = document.getElementById("addQtyInput");
        if (addQty) addQty.value = res.finalArea;
        closeTileCalculator();
        posNotify(`Hisoblangan ${res.finalArea} m² kiritildi. Kafelni tanlang va qo'shing.`, "info");
    }
}

// Fast Quantity Selector Presets
function setScannedQty(qty) {
    const input = document.getElementById("addQtyInput");
    if (input) input.value = qty;
}

function setScannedQtyByBoxes(boxCount) {
    const input = document.getElementById("addQtyInput");
    if (!input) return;
    const boxSize = (currentScannedProduct && currentScannedProduct.box_size_m2) ? currentScannedProduct.box_size_m2 : 1.44;
    input.value = (boxCount * boxSize).toFixed(2);
}

function setScannedMaxQty() {
    const input = document.getElementById("addQtyInput");
    if (!input || !currentScannedProduct) return;
    input.value = currentScannedProduct.quantity_in_stock || 1;
}

// ---------------- SHOWROOM INSTANT CATALOG ----------------

let cachedCatalogProducts = [];

async function loadShowroomCatalog(q = "", size = "") {
    const container = document.getElementById("showroomCatalogGrid");
    if (!container) return;

    // Reset standard filter buttons and highlight active
    const chips = document.querySelectorAll("#catalogFilterChips button");
    chips.forEach(b => {
        b.className = "catalog-filter-btn px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition";
    });
    const defBtn = document.getElementById("filterDefectsBtn");
    if (defBtn) {
        defBtn.className = "catalog-filter-btn px-2.5 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 font-bold border border-rose-200 shadow-2xs transition flex items-center space-x-1";
    }

    if (!size && !q) {
        const allBtn = document.getElementById("filterAllBtn");
        if (allBtn) allBtn.className = "catalog-filter-btn px-2.5 py-1 rounded-lg bg-slate-900 text-white shadow-2xs";
    } else if (size) {
        chips.forEach(b => {
            if (b.innerText.trim() === size.trim()) {
                b.className = "catalog-filter-btn px-2.5 py-1 rounded-lg bg-slate-900 text-white shadow-2xs";
            }
        });
    }

    try {
        const url = `/api/products/search?q=${encodeURIComponent(q)}&size=${encodeURIComponent(size)}&limit=30`;
        const res = await fetch(url);
        const data = await res.json();

        if (!data.success || !data.products || data.products.length === 0) {
            container.innerHTML = `
                <div class="col-span-full text-center py-8 text-slate-400">
                    <i class="fa-solid fa-shapes text-3xl mb-2 text-slate-300"></i>
                    <p class="text-xs font-bold">Kafellar topilmadi</p>
                </div>
            `;
            cachedCatalogProducts = [];
            return;
        }

        cachedCatalogProducts = data.products;
        renderCatalogCards(cachedCatalogProducts);
    } catch (e) {
        console.error("Showroom yuklashda xato:", e);
    }
}

function filterCatalogInstant(query) {
    const container = document.getElementById("showroomCatalogGrid");
    if (!container) return;
    query = (query || "").trim().toLowerCase();
    if (!query) {
        renderCatalogCards(cachedCatalogProducts);
        return;
    }
    const filtered = cachedCatalogProducts.filter(p => {
        const brand = (p.brand || "").toLowerCase();
        const model = (p.model_name || "").toLowerCase();
        const sku = (p.sku || "").toLowerCase();
        const size = (p.size || "").toLowerCase();
        return brand.includes(query) || model.includes(query) || sku.includes(query) || size.includes(query);
    });
    renderCatalogCards(filtered);
}

function renderCatalogCards(products) {
    const container = document.getElementById("showroomCatalogGrid");
    if (!container) return;

    if (!products || products.length === 0) {
        container.innerHTML = `
            <div class="col-span-full text-center py-8 text-slate-400">
                <i class="fa-solid fa-magnifying-glass text-2xl mb-2 text-slate-300"></i>
                <p class="text-xs font-bold">Qidiruv bo'yicha kafel topilmadi</p>
            </div>
        `;
        return;
    }

    let html = "";
    products.forEach(p => {
        const isOutOfStock = p.quantity_in_stock <= 0;
        const boxSize = p.box_size_m2 || 1.44;
        const imgHtml = p.image_path
            ? `<img src="${p.image_path}" class="max-h-full max-w-full object-contain rounded transition group-hover:scale-105 duration-200" alt="${p.model_name}">`
            : `<div class="flex flex-col items-center justify-center text-slate-400 select-none py-2">
                   <div class="w-9 h-9 rounded-xl bg-white border border-slate-200 flex items-center justify-center text-slate-400 mb-1 shadow-2xs group-hover:text-sky-600 transition">
                       <i class="fa-solid fa-shapes text-base"></i>
                   </div>
                   <span class="text-[10px] font-bold text-slate-500 uppercase tracking-wider">${p.brand}</span>
               </div>`;

        html += `
        <div class="bg-white rounded-2xl p-3 border border-slate-200/90 hover:border-sky-400 hover:shadow-md transition-all flex flex-col justify-between shadow-2xs group">
            <div>
                <div class="relative h-28 rounded-xl bg-slate-50 border border-slate-100 overflow-hidden mb-2 cursor-pointer flex items-center justify-center p-1" onclick="selectProductFromCatalog(${JSON.stringify(p).replace(/"/g, '&quot;')})">
                    ${imgHtml}
                    <span class="absolute top-1.5 left-1.5 bg-white/95 backdrop-blur-xs text-slate-800 border border-slate-200/80 text-[9px] font-black uppercase px-2 py-0.5 rounded shadow-2xs">
                        ${p.brand}
                    </span>
                    <span class="absolute bottom-1.5 right-1.5 text-[9px] font-bold px-2 py-0.5 rounded shadow-2xs ${isOutOfStock ? 'bg-rose-600 text-white' : 'bg-emerald-600 text-white'}">
                        ${p.quantity_in_stock} ${p.unit}
                    </span>
                </div>
                <h4 class="font-bold text-xs text-slate-900 leading-tight truncate cursor-pointer group-hover:text-sky-600 transition" title="${p.brand} ${p.model_name}" onclick="selectProductFromCatalog(${JSON.stringify(p).replace(/"/g, '&quot;')})">${p.model_name}</h4>
                <div class="flex items-center justify-between mt-1 text-[11px]">
                    <span class="font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded text-[10px]">${p.size}</span>
                    <span class="font-black text-slate-900 text-xs">${Number(p.price).toLocaleString('ru-RU')} <span class="text-[10px] font-normal text-slate-500">so'm</span></span>
                </div>
            </div>

            <div class="mt-2.5 pt-2 border-t border-slate-100 flex items-center gap-1.5">
                <button type="button" onclick="selectProductFromCatalog(${JSON.stringify(p).replace(/"/g, '&quot;')})" class="px-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-[11px] py-1.5 rounded-lg transition" title="Batafsil ko'rish">
                    Ko'rish
                </button>
                <button type="button" onclick="quickAddFromCatalog(this, ${JSON.stringify(p).replace(/"/g, '&quot;')})" class="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-black text-[11px] py-1.5 rounded-lg transition flex items-center justify-center space-x-1 shadow-2xs" title="1 quti (${boxSize} m²) savatga qo'shish">
                    <i class="fa-solid fa-cart-plus text-[10px]"></i>
                    <span>+ Savatga</span>
                </button>
            </div>
        </div>
        `;
    });

    container.innerHTML = html;
}

function quickAddFromCatalog(btn, product) {
    const qty = product.box_size_m2 || 1.44;
    addProductToCartData(product, qty);
    
    // Tactile button animation feedback
    const originalText = btn.innerHTML;
    btn.className = "flex-1 bg-sky-600 text-white font-black text-[11px] py-1.5 rounded-lg transition flex items-center justify-center space-x-1 shadow-xs animate-pulse";
    btn.innerHTML = `<i class="fa-solid fa-check text-[10px]"></i> <span>Qo'shildi!</span>`;
    setTimeout(() => {
        btn.className = "flex-1 bg-emerald-600 hover:bg-emerald-500 text-white font-black text-[11px] py-1.5 rounded-lg transition flex items-center justify-center space-x-1 shadow-xs";
        btn.innerHTML = originalText;
    }, 900);
}

function selectProductFromCatalog(product) {
    displayScannedProduct(product);
}

// ---------------- DEFECTS / BROKEN TILES CATALOG ----------------

async function loadDefectsCatalog() {
    const container = document.getElementById("showroomCatalogGrid");
    if (!container) return;

    // Reset standard filter buttons and highlight defect filter button
    const chips = document.querySelectorAll("#catalogFilterChips button");
    chips.forEach(b => {
        b.className = "catalog-filter-btn px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition";
    });
    const defBtn = document.getElementById("filterDefectsBtn");
    if (defBtn) {
        defBtn.className = "catalog-filter-btn px-2.5 py-1 rounded-lg bg-rose-600 text-white font-bold shadow-2xs transition flex items-center space-x-1";
    }

    try {
        const res = await fetch("/api/defects/for-sale");
        const data = await res.json();

        if (!data.success || !data.defects || data.defects.length === 0) {
            container.innerHTML = `
                <div class="col-span-full text-center py-8 bg-slate-50 rounded-2xl border border-dashed border-slate-200">
                    <i class="fa-solid fa-heart-crack text-3xl mb-2 text-rose-400"></i>
                    <p class="text-xs font-bold text-slate-700">Hozirda sotuvga chiqarilgan siniq yoki brak kafellar yo'q</p>
                    <p class="text-[11px] text-slate-400 mt-0.5">Ombordan yangi siniqlar kiritilganda bu yerda ko'rinadi</p>
                </div>
            `;
            return;
        }

        let html = "";
        data.defects.forEach(d => {
            const origPrice = Number(d.original_price) || 0;
            const discPrice = Number(d.discounted_price) || 0;
            const discountPct = origPrice > 0 ? Math.max(5, Math.round((1 - (discPrice / origPrice)) * 100)) : 50;
            const imgHtml = d.image_path
                ? `<img src="${d.image_path}" class="max-h-full max-w-full object-contain rounded transition group-hover:scale-105 duration-200">`
                : `<div class="flex flex-col items-center justify-center text-rose-400 select-none py-2">
                       <i class="fa-solid fa-heart-crack text-2xl mb-1 text-rose-300"></i>
                       <span class="text-[10px] font-bold text-rose-700 uppercase">${d.brand}</span>
                   </div>`;

            html += `
            <div class="bg-gradient-to-b from-white to-rose-50/30 rounded-2xl p-3 border border-rose-200 hover:border-rose-300 hover:shadow-md transition-all flex flex-col justify-between shadow-2xs relative group">
                <span class="absolute top-2 right-2 bg-rose-600 text-white text-[9px] font-black uppercase px-2 py-0.5 rounded-full shadow-2xs z-10">
                    -${discountPct}% ARZON
                </span>
                <div>
                    <div class="relative h-28 rounded-xl bg-slate-900/5 overflow-hidden mb-2 border border-rose-100 flex items-center justify-center p-1 cursor-pointer" onclick='selectProductFromCatalog(${JSON.stringify(d).replace(/'/g, "&apos;")})'>
                        ${imgHtml}
                        <span class="absolute top-1.5 left-1.5 bg-white/95 text-slate-800 border border-slate-200 text-[9px] font-black uppercase px-2 py-0.5 rounded shadow-2xs">
                            ${d.brand}
                        </span>
                        <span class="absolute bottom-1.5 right-1.5 text-[9px] font-bold px-2 py-0.5 rounded shadow-2xs bg-rose-600 text-white">
                            💔 ${d.quantity} ${d.unit}
                        </span>
                    </div>
                    <div class="flex items-center space-x-1 mb-0.5">
                        <span class="text-[9px] font-black uppercase bg-rose-100 text-rose-700 px-1 rounded">💔 Siniq</span>
                        <span class="text-[9px] text-slate-400 truncate" title="${d.reason}">${d.reason}</span>
                    </div>
                    <h4 class="font-bold text-xs text-slate-900 leading-tight truncate cursor-pointer group-hover:text-rose-600 transition" title="${d.brand} ${d.model_name}" onclick='selectProductFromCatalog(${JSON.stringify(d).replace(/'/g, "&apos;")})'>${d.model_name}</h4>
                    <div class="mt-1 flex items-baseline justify-between text-[11px]">
                        <span class="font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded text-[10px]">${d.size}</span>
                        <div class="text-right">
                            <del class="text-[9px] text-slate-400 block">${origPrice.toLocaleString('ru-RU')} s.</del>
                            <span class="font-black text-rose-600 text-xs">${discPrice.toLocaleString('ru-RU')} s.</span>
                        </div>
                    </div>
                </div>

                <div class="mt-2.5 pt-2 border-t border-rose-100 flex items-center gap-1.5">
                    <button type="button" onclick='quickAddDefectToCart(this, ${JSON.stringify(d).replace(/'/g, "&apos;")})' class="flex-1 bg-rose-600 hover:bg-rose-500 text-white font-black text-[11px] py-1.5 rounded-lg transition flex items-center justify-center space-x-1 shadow-2xs" title="Siniq kafelni savatga qo'shish">
                        <i class="fa-solid fa-cart-plus text-[10px]"></i>
                        <span>+ Savatga Qo'shish</span>
                    </button>
                </div>
            </div>
            `;
        });

        container.innerHTML = html;
    } catch (err) {
        console.error("Siniqlarni yuklashda xato:", err);
    }
}

function quickAddDefectToCart(btn, defect) {
    const productObj = {
        id: defect.product_id,
        product_id: defect.product_id,
        defect_id: defect.id,
        is_defect: 1,
        brand: defect.brand,
        model_name: defect.model_name + " [💔 Siniq/Brak]",
        sku: `BRAK-${defect.id}`,
        size: defect.size,
        unit: defect.unit,
        price: Number(defect.discounted_price || 0),
        discounted_price: Number(defect.discounted_price || 0),
        quantity: defect.quantity,
        stock: defect.quantity,
        quantity_in_stock: defect.quantity,
        box_size_m2: defect.box_size_m2 || 1.44,
        image_path: defect.image_path
    };
    const qty = Math.min(1, defect.quantity);
    addProductToCartData(productObj, qty);

    if (btn) {
        const originalText = btn.innerHTML;
        btn.className = "flex-1 bg-emerald-600 text-white font-black text-[11px] py-1.5 rounded-lg transition flex items-center justify-center space-x-1 shadow-xs animate-pulse";
        btn.innerHTML = `<i class="fa-solid fa-check text-[10px]"></i> <span>Qo'shildi!</span>`;
        setTimeout(() => {
            btn.className = "flex-1 bg-rose-600 hover:bg-rose-500 text-white font-black text-[11px] py-1.5 rounded-lg transition flex items-center justify-center space-x-1 shadow-xs";
            btn.innerHTML = originalText;
        }, 900);
    }
}


// ---------------- KASSA & CHECKOUT PAGE / MODAL LOGIC ----------------

function openCheckoutModal() {
    const cart = getCart();
    if (!cart || cart.length === 0) {
        posNotify("Savatda kafel yo'q! Avval mahsulot tanlang yoki skanerlang.", "warning");
        return;
    }

    const modal = document.getElementById("checkoutModal");
    if (!modal) {
        window.location.href = "/kassa";
        return;
    }

    renderKassaPage();
    modal.classList.remove("hidden");
    modal.classList.add("flex");

    // Ensure payment method checked
    const checkedMethod = document.querySelector('input[name="paymentMethod"]:checked');
    if (!checkedMethod) {
        const naqdRadio = document.querySelector('input[name="paymentMethod"][value="naqd"]');
        if (naqdRadio) {
            naqdRadio.checked = true;
            togglePaymentInputs("naqd");
        }
    } else {
        togglePaymentInputs(checkedMethod.value);
    }

    setupCustomerPhoneFormatting();

    // Default cash given to exact total
    setExactCash();

    setTimeout(() => {
        const nameInput = document.getElementById("customerName");
        if (nameInput) nameInput.focus();
    }, 150);
}

function closeCheckoutModal() {
    const modal = document.getElementById("checkoutModal");
    if (modal) {
        modal.classList.add("hidden");
        modal.classList.remove("flex");
    }
}

function setupCustomerPhoneFormatting() {
    const phoneInput = document.getElementById("customerPhone");
    if (phoneInput && !phoneInput.dataset.formatted) {
        phoneInput.dataset.formatted = "true";
        phoneInput.addEventListener("input", (e) => {
            let x = e.target.value.replace(/\D/g, '');
            if (x.startsWith('998')) x = x.substring(3);
            x = x.substring(0, 9);
            let formatted = '+998';
            if (x.length > 0) formatted += ' (' + x.substring(0, 2);
            if (x.length >= 2) formatted += ') ';
            if (x.length > 2) formatted += x.substring(2, 5);
            if (x.length >= 5) formatted += '-' + x.substring(5, 7);
            if (x.length >= 7) formatted += '-' + x.substring(7, 9);
            e.target.value = formatted;
        });
    }
}

function renderKassaPage() {
    const tableBody = document.getElementById("kassaTableBody");
    const totalSumEl = document.getElementById("kassaTotalSum");
    const subtotalEl = document.getElementById("kassaSubtotal");
    const emptyState = document.getElementById("kassaEmptyState");
    const mainContent = document.getElementById("kassaMainContent");

    if (!tableBody) return;

    const cart = getCart();

    if (cart.length === 0) {
        if (emptyState) emptyState.classList.remove("hidden");
        if (mainContent) mainContent.classList.add("hidden");
        tableBody.innerHTML = `<tr><td colspan="4" class="text-center py-6 text-slate-400 text-xs font-bold">Savat bo'sh</td></tr>`;
        if (subtotalEl) subtotalEl.innerText = "0 so'm";
        if (totalSumEl) totalSumEl.innerText = "0";
        return;
    }

    if (emptyState) emptyState.classList.add("hidden");
    if (mainContent) mainContent.classList.remove("hidden");

    let html = "";
    let grandTotal = 0;

    cart.forEach((item, index) => {
        const itemTotal = item.qty * item.price;
        grandTotal += itemTotal;

        html += `
        <tr class="hover:bg-slate-50 transition">
            <td class="py-2.5 px-2 flex items-center space-x-2">
                <div class="w-8 h-8 rounded-lg bg-white overflow-hidden border border-slate-200 flex-shrink-0 relative flex items-center justify-center p-0.5">
                    <img src="${item.image_path || '/static/placeholder-tile.png'}" class="max-h-full max-w-full object-contain">
                    ${item.is_defect ? '<span class="absolute bottom-0 inset-x-0 bg-rose-600 text-white text-[7px] font-black text-center uppercase leading-tight">Brak</span>' : ''}
                </div>
                <div class="min-w-0">
                    <div class="flex items-center space-x-1">
                        <span class="text-[9px] font-black uppercase text-sky-600 truncate">${item.brand}</span>
                        ${item.is_defect ? '<span class="text-[8px] font-black uppercase bg-rose-100 text-rose-700 px-1 rounded">💔 Siniq</span>' : ''}
                    </div>
                    <h4 class="font-bold text-xs text-slate-800 truncate">${item.model_name}</h4>
                    <span class="text-[9px] text-slate-400 font-mono">${item.size}</span>
                </div>
            </td>
            <td class="py-2.5 px-2 text-center whitespace-nowrap">
                <div class="inline-flex items-center bg-slate-100 rounded-lg p-0.5">
                    <button onclick="updateCartItemByIndex(${index}, -1)" class="w-4 h-4 rounded hover:bg-white text-xs font-bold text-slate-700">-</button>
                    <span class="px-1.5 font-mono font-bold text-xs text-slate-900">${item.qty} ${item.unit}</span>
                    <button onclick="updateCartItemByIndex(${index}, 1)" class="w-4 h-4 rounded hover:bg-white text-xs font-bold text-slate-700">+</button>
                </div>
            </td>
            <td class="py-2.5 px-2 text-right text-xs font-black font-mono text-slate-900 whitespace-nowrap">
                ${Number(itemTotal).toLocaleString('ru-RU')}
            </td>
            <td class="py-2.5 px-1 text-center">
                <button onclick="removeCartItemByIndex(${index})" class="text-slate-300 hover:text-rose-500 transition text-xs" title="O'chirish">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </td>
        </tr>
        `;
    });

    tableBody.innerHTML = html;
    if (subtotalEl) subtotalEl.innerText = Number(grandTotal).toLocaleString("ru-RU") + " so'm";
    
    const finalTotal = Math.max(0, grandTotal - currentDiscountAmount);
    if (totalSumEl) totalSumEl.innerText = Number(finalTotal).toLocaleString("ru-RU");

    calcChange();
    calcNasiyaDebt();
}

function setFastCash(amount) {
    const input = document.getElementById("cashGivenInput");
    if (!input) return;
    const current = parseFloat(input.value) || 0;
    input.value = current + amount;
    calcChange();
}

function setExactCash() {
    const input = document.getElementById("cashGivenInput");
    if (!input) return;
    const cart = getCart();
    const grandTotal = cart.reduce((sum, item) => sum + (item.qty * item.price), 0);
    const finalTotal = Math.max(0, grandTotal - currentDiscountAmount);
    input.value = finalTotal;
    calcChange();
}

function applyDiscount(percent = 0, fixedSum = 0) {
    const cart = getCart();
    const subtotal = cart.reduce((sum, item) => sum + (item.qty * item.price), 0);
    
    if (percent > 0) {
        currentDiscountAmount = Math.round((subtotal * percent) / 100);
    } else if (fixedSum > 0) {
        currentDiscountAmount = fixedSum;
    } else {
        currentDiscountAmount = 0;
    }

    const discLabel = document.getElementById("discountDisplay");
    if (discLabel) {
        discLabel.innerText = `${Number(currentDiscountAmount).toLocaleString('ru-RU')} so'm`;
    }

    renderKassaPage();
    posNotify(`Chegirma: ${Number(currentDiscountAmount).toLocaleString('ru-RU')} so'm belgilandi`, "info");
}

function togglePaymentInputs(method) {
    const cashBlock = document.getElementById("cashCalcBlock");
    const nasiyaBlock = document.getElementById("nasiyaCalcBlock");
    const payBtnText = document.getElementById("payBtnText");

    if (cashBlock) {
        if (method === "naqd") {
            cashBlock.classList.remove("hidden");
        } else {
            cashBlock.classList.add("hidden");
        }
    }

    if (nasiyaBlock) {
        if (method === "nasiya") {
            nasiyaBlock.classList.remove("hidden");
            calcNasiyaDebt();
            if (payBtnText) payBtnText.innerText = "NASIYAGA RASMIYLASHTIRISH";
        } else {
            nasiyaBlock.classList.add("hidden");
            if (payBtnText) payBtnText.innerText = "TO'LOV QILINDI (Tasdiqlash)";
        }
    }
}

function calcNasiyaDebt() {
    const advInput = document.getElementById("nasiyaAdvanceInput");
    const outEl = document.getElementById("nasiyaDebtOutput");
    if (!outEl) return;

    const cart = getCart();
    const grandTotal = cart.reduce((sum, item) => sum + (item.qty * item.price), 0);
    const finalTotal = Math.max(0, grandTotal - currentDiscountAmount);
    const advance = parseFloat(advInput ? advInput.value : 0) || 0;
    const debt = Math.max(0, finalTotal - advance);

    outEl.innerText = Number(debt).toLocaleString('ru-RU') + " so'm";
}

let customerSearchTimer = null;
function searchCustomersForKassa(query) {
    clearTimeout(customerSearchTimer);
    const dropdown = document.getElementById("customerSearchDropdown");
    if (!dropdown) return;

    if (!query || query.trim().length < 1) {
        dropdown.classList.add("hidden");
        return;
    }

    customerSearchTimer = setTimeout(async () => {
        try {
            const res = await fetch(`/api/customers/search?q=${encodeURIComponent(query.trim())}`);
            const data = await res.json();
            if (data.success && data.customers.length > 0) {
                let html = "";
                data.customers.forEach(c => {
                    html += `
                    <div onclick="selectCustomerForKassa(${c.id}, '${c.full_name.replace(/'/g, "\\'")}', '${c.phone || ''}', ${c.balance_debt})" class="p-2.5 hover:bg-amber-50 cursor-pointer flex justify-between items-center transition">
                        <div>
                            <span class="font-bold text-slate-800">${c.full_name}</span>
                            <span class="text-[10px] text-slate-400 block">${c.phone || 'Tel kiritilmagan'} &bull; ${c.customer_type}</span>
                        </div>
                        <div class="text-right">
                            <span class="text-[10px] font-bold ${c.balance_debt > 0 ? 'text-rose-600' : 'text-emerald-600'}">
                                ${c.balance_debt > 0 ? 'Qarz: ' + Number(c.balance_debt).toLocaleString('ru-RU') + ' s.' : 'Qarzsiz'}
                            </span>
                        </div>
                    </div>
                    `;
                });
                dropdown.innerHTML = html;
                dropdown.classList.remove("hidden");
            } else {
                dropdown.classList.add("hidden");
            }
        } catch (e) {
            dropdown.classList.add("hidden");
        }
    }, 200);
}

function selectCustomerForKassa(id, name, phone, debt) {
    const nameInput = document.getElementById("customerName");
    const phoneInput = document.getElementById("customerPhone");
    const idInput = document.getElementById("customerId");
    const dropdown = document.getElementById("customerSearchDropdown");

    if (nameInput) nameInput.value = name;
    if (phoneInput && phone) phoneInput.value = phone;
    if (idInput) idInput.value = id;
    if (dropdown) dropdown.classList.add("hidden");

    posNotify(`Mijoz tanlandi: ${name} (Qarz: ${Number(debt).toLocaleString('ru-RU')} so'm)`, "info");
}

// Close customer dropdown when clicking outside
document.addEventListener("click", (e) => {
    const dropdown = document.getElementById("customerSearchDropdown");
    const nameInput = document.getElementById("customerName");
    if (dropdown && !dropdown.contains(e.target) && e.target !== nameInput) {
        dropdown.classList.add("hidden");
    }
});

// --- USTA / PRORAB SELECTION & QUICK-ADD ---
let ustaSearchTimer = null;
function searchUstalarForKassa(query) {
    clearTimeout(ustaSearchTimer);
    const dropdown = document.getElementById("ustaSearchDropdown");
    if (!dropdown) return;

    ustaSearchTimer = setTimeout(async () => {
        try {
            const url = query && query.trim().length > 0
                ? `/api/ustalar?q=${encodeURIComponent(query.trim())}`
                : `/api/ustalar`;
            const res = await fetch(url);
            const data = await res.json();
            if (data.success && data.ustalar.length > 0) {
                let html = "";
                data.ustalar.forEach(u => {
                    html += `
                    <div onclick="selectUstaForKassa(${u.id}, '${u.full_name.replace(/'/g, "\\'")}', '${u.phone || ''}')" class="p-2.5 hover:bg-amber-50 cursor-pointer flex justify-between items-center transition">
                        <div>
                            <span class="font-bold text-slate-800 text-xs">👷 ${u.full_name}</span>
                            <span class="text-[10px] text-slate-400 block">${u.phone || 'Tel kiritilmagan'} &bull; ${u.customer_type}</span>
                        </div>
                        <span class="text-[10px] bg-amber-100 text-amber-800 font-bold px-1.5 py-0.5 rounded">Tanlash</span>
                    </div>
                    `;
                });
                dropdown.innerHTML = html;
                dropdown.classList.remove("hidden");
            } else {
                dropdown.innerHTML = `
                    <div class="p-3 text-center text-slate-400 text-xs">
                        Usta topilmadi. 
                        <button type="button" onclick="openQuickAddUstaModal()" class="text-sky-600 font-bold block mt-1 hover:underline">+ Yangi usta qo'shish</button>
                    </div>
                `;
                dropdown.classList.remove("hidden");
            }
        } catch (e) {
            dropdown.classList.add("hidden");
        }
    }, 150);
}

function selectUstaForKassa(id, name, phone) {
    const idInput = document.getElementById("checkoutUstaId");
    const searchInput = document.getElementById("ustaSearchInput");
    const dropdown = document.getElementById("ustaSearchDropdown");
    const badge = document.getElementById("selectedUstaBadge");
    const nameSpan = document.getElementById("selectedUstaName");
    const phoneSpan = document.getElementById("selectedUstaPhone");

    if (idInput) idInput.value = id;
    if (searchInput) searchInput.value = name;
    if (nameSpan) nameSpan.innerText = name;
    if (phoneSpan) phoneSpan.innerText = phone ? `(${phone})` : "";
    if (badge) badge.classList.remove("hidden");
    if (dropdown) dropdown.classList.add("hidden");

    posNotify(`Usta biriktirildi: ${name}`, "info");
}

function clearSelectedUsta() {
    const idInput = document.getElementById("checkoutUstaId");
    const searchInput = document.getElementById("ustaSearchInput");
    const badge = document.getElementById("selectedUstaBadge");

    if (idInput) idInput.value = "";
    if (searchInput) searchInput.value = "";
    if (badge) badge.classList.add("hidden");
}

function openQuickAddUstaModal() {
    const modal = document.getElementById("quickAddUstaModal");
    const searchInput = document.getElementById("ustaSearchInput");
    const nameInput = document.getElementById("quickUstaName");
    if (modal) {
        modal.classList.remove("hidden");
        modal.classList.add("flex");
        if (nameInput && searchInput && searchInput.value) {
            nameInput.value = searchInput.value;
        }
        if (nameInput) setTimeout(() => nameInput.focus(), 100);
    }
}

function closeQuickAddUstaModal() {
    const modal = document.getElementById("quickAddUstaModal");
    if (modal) {
        modal.classList.add("hidden");
        modal.classList.remove("flex");
    }
}

async function submitQuickAddUsta() {
    const nameInput = document.getElementById("quickUstaName");
    const phoneInput = document.getElementById("quickUstaPhone");
    const notesInput = document.getElementById("quickUstaNotes");

    const full_name = nameInput?.value?.trim();
    const phone = phoneInput?.value?.trim();
    const notes = notesInput?.value?.trim();

    if (!full_name) {
        posNotify("Usta ismini kiriting!", "warning");
        return;
    }

    try {
        const res = await fetch("/api/ustalar/quick-add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ full_name, phone, notes })
        });
        const data = await res.json();
        if (data.success) {
            posNotify("✅ Yangi usta qo'shildi!", "success");
            selectUstaForKassa(data.usta.id, data.usta.full_name, data.usta.phone);
            closeQuickAddUstaModal();
            if (nameInput) nameInput.value = "";
            if (phoneInput) phoneInput.value = "";
            if (notesInput) notesInput.value = "";
        } else {
            posNotify(data.message || "Xatolik yuz berdi", "danger");
        }
    } catch (e) {
        posNotify("Server bilan aloqa xatosi!", "danger");
    }
}

// Close usta dropdown when clicking outside
document.addEventListener("click", (e) => {
    const dropdown = document.getElementById("ustaSearchDropdown");
    const searchInput = document.getElementById("ustaSearchInput");
    if (dropdown && !dropdown.contains(e.target) && e.target !== searchInput) {
        dropdown.classList.add("hidden");
    }
});

function calcChange() {
    const cashInput = document.getElementById("cashGivenInput");
    const changeOutput = document.getElementById("cashChangeOutput");
    if (!cashInput || !changeOutput) return;

    const cart = getCart();
    const grandTotal = cart.reduce((sum, item) => sum + (item.qty * item.price), 0);
    const finalTotal = Math.max(0, grandTotal - currentDiscountAmount);
    const given = parseFloat(cashInput.value) || 0;

    if (given >= finalTotal) {
        const change = given - finalTotal;
        changeOutput.innerText = `${Number(change).toLocaleString('ru-RU')} so'm`;
        changeOutput.className = "text-base font-black text-emerald-800";
    } else {
        const diff = finalTotal - given;
        changeOutput.innerText = `Yetmayapti: ${Number(diff).toLocaleString('ru-RU')} so'm`;
        changeOutput.className = "text-sm font-bold text-rose-600";
    }
}

async function submitPayment() {
    const cart = getCart();
    if (cart.length === 0) {
        posNotify("Savat bo'sh! Avval mahsulot tanlang.", "warning");
        return;
    }

    const payBtn = document.getElementById("payNowBtn");
    const customerName = document.getElementById("customerName")?.value || "Mijoz";
    const customerPhone = document.getElementById("customerPhone")?.value || "";
    const customerId = document.getElementById("customerId")?.value || null;
    const rawUstaId = document.getElementById("checkoutUstaId")?.value;
    const ustaId = rawUstaId ? parseInt(rawUstaId) : null;
    const paymentMethodEl = document.querySelector('input[name="paymentMethod"]:checked');
    const paymentMethod = paymentMethodEl ? paymentMethodEl.value : "naqd";
    const cashierNote = document.getElementById("cashierNote")?.value || "";

    const grandTotal = cart.reduce((sum, item) => sum + (item.qty * item.price), 0);
    const finalTotal = Math.max(0, grandTotal - currentDiscountAmount);

    const isNasiya = paymentMethod === "nasiya" ? 1 : 0;
    const advInput = document.getElementById("nasiyaAdvanceInput");
    const advanceAmount = isNasiya ? (parseFloat(advInput ? advInput.value : 0) || 0) : finalTotal;
    const debtAmount = isNasiya ? Math.max(0, finalTotal - advanceAmount) : 0;

    const executeCheckout = async () => {
        if (payBtn) {
            payBtn.disabled = true;
            payBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-xl"></i> <span>To'lov qabul qilinmoqda...</span>`;
        }

        try {
            const response = await fetch("/api/checkout", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    customer_name: customerName,
                    customer_phone: customerPhone,
                    customer_id: customerId,
                    usta_id: ustaId,
                    payment_method: paymentMethod,
                    is_nasiya: isNasiya,
                    paid_amount: advanceAmount,
                    debt_amount: debtAmount,
                    cashier_note: cashierNote,
                    discount_amount: currentDiscountAmount,
                    items: cart
                })
            });

            const data = await response.json();

            if (data.success) {
                localStorage.removeItem(CART_STORAGE_KEY);
                localStorage.removeItem(getCartStorageKey(currentCartTab));
                currentDiscountAmount = 0;
                posNotify(`✅ ${isNasiya ? 'Nasiya rasmiylashtirildi' : "To'lov qabul qilindi"}! Nakladnoy: ${data.order_number}`, "success");
                setTimeout(() => {
                    window.location.href = `/nakladnoy/${data.order_id}`;
                }, 500);
            } else {
                posNotify(`❌ Xatolik: ${data.message}`, "danger");
                if (payBtn) {
                    payBtn.disabled = false;
                    payBtn.innerHTML = `<i class="fa-solid fa-circle-check text-xl"></i> <span>TO'LOV QILINDI (Tasdiqlash)</span>`;
                }
            }
        } catch (err) {
            posNotify(`Server xatosi: ${err.message}`, "danger");
            if (payBtn) {
                payBtn.disabled = false;
                payBtn.innerHTML = `<i class="fa-solid fa-circle-check text-xl"></i> <span>TO'LOV QILINDI (Tasdiqlash)</span>`;
            }
        }
    };

    if (typeof showConfirmModal === "function") {
        let methodLabel = "💵 Naqd Pul";
        if (paymentMethod === "karta") methodLabel = "💳 Plastik Karta";
        if (paymentMethod === "nasiya") methodLabel = "⚠️ Nasiya (Qarzga)";

        const summaryHtml = `
            <div class="space-y-2">
                <div class="flex justify-between items-center text-slate-600">
                    <span class="font-medium">Mijoz:</span>
                    <span class="font-bold text-slate-900">${customerName}</span>
                </div>
                <div class="flex justify-between items-center text-slate-600">
                    <span class="font-medium">To'lov turi:</span>
                    <span class="font-bold text-slate-900">${methodLabel}</span>
                </div>
                ${isNasiya ? `
                <div class="flex justify-between items-center text-slate-600">
                    <span class="font-medium">To'langan avans:</span>
                    <span class="font-bold text-emerald-600 font-mono">${Number(advanceAmount).toLocaleString('ru-RU')} so'm</span>
                </div>
                <div class="flex justify-between items-center text-slate-600">
                    <span class="font-medium">Qarzga yoziladi:</span>
                    <span class="font-bold text-rose-600 font-mono">${Number(debtAmount).toLocaleString('ru-RU')} so'm</span>
                </div>
                ` : ''}
                <div class="flex justify-between items-center text-slate-600">
                    <span class="font-medium">Mahsulotlar:</span>
                    <span class="font-bold text-slate-900">${cart.length} xil kafel</span>
                </div>
                <div class="flex justify-between items-baseline pt-2 border-t border-slate-200">
                    <span class="font-bold text-slate-800 text-xs uppercase">Jami Buyurtma:</span>
                    <span class="text-xl font-black text-slate-900 font-mono">${Number(finalTotal).toLocaleString('ru-RU')} so'm</span>
                </div>
            </div>
        `;
        showConfirmModal({
            title: isNasiya ? "Nasiyani Tasdiqlash" : "To'lovni Tasdiqlash",
            message: "Ushbu buyurtmani yakunlaysizmi? Mahsulotlar ombordan ayriladi va Nakladnoy shakllanadi.",
            html: summaryHtml,
            icon: isNasiya ? "fa-solid fa-hand-holding-dollar text-amber-500" : "fa-solid fa-cash-register text-emerald-600",
            confirmText: isNasiya ? "Nasiyani Tasdiqlash" : "To'lovni Tasdiqlash",
            confirmClass: isNasiya ? "px-5 py-2.5 rounded-xl text-xs font-black bg-amber-600 hover:bg-amber-500 text-white shadow-md transition" : "px-5 py-2.5 rounded-xl text-xs font-black bg-emerald-600 hover:bg-emerald-500 text-white shadow-md transition",
            onConfirm: executeCheckout
        });
    } else {
        if (confirm("Buyurtmani tasdiqlaysizmi?")) {
            executeCheckout();
        }
    }
}

// Auto update on load
document.addEventListener("DOMContentLoaded", async () => {
    updateCartUI();
    
    // Check if defect_id passed in URL (from /ombor/siniqlar "Sotish" button)
    const urlParams = new URLSearchParams(window.location.search);
    const defectIdParam = urlParams.get('defect_id');

    if (defectIdParam) {
        try {
            await loadDefectsCatalog();
            const res = await fetch("/api/defects/for-sale");
            const data = await res.json();
            if (data.success && data.defects) {
                const targetDefect = data.defects.find(d => String(d.id) === String(defectIdParam));
                if (targetDefect) {
                    quickAddDefectToCart(null, targetDefect);
                    posNotify(`💔 Siniq kafel (${targetDefect.brand} ${targetDefect.model_name}) savatga qo'shildi!`, "success");
                }
            }
        } catch (e) {
            console.error("Defect auto-add error:", e);
        }
    } else if (document.getElementById("showroomCatalogGrid")) {
        loadShowroomCatalog();
    }

    // Auto open checkout modal if ?checkout=1 requested
    const checkoutParam = urlParams.get('checkout');
    if (checkoutParam === '1') {
        setTimeout(() => {
            openCheckoutModal();
        }, 300);
    }

    setupCustomerPhoneFormatting();
});

// Shortcuts: Ctrl+Enter to submit payment, Esc to close checkout modal
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        closeCheckoutModal();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        const modal = document.getElementById("checkoutModal");
        if ((modal && !modal.classList.contains("hidden")) || window.location.pathname === "/kassa") {
            e.preventDefault();
            submitPayment();
        }
    }
});


