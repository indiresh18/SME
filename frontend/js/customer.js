/* SME Anchor Mart - Customer portal */
requireRole("customer");

const CATEGORY_ICONS = {
  Staples: "🌾", Beverages: "🥤", Dairy: "🥛", Snacks: "🍪",
  Household: "🧺", "Personal Care": "🧴", Bakery: "🍞", Spices: "🌶️",
};

const state = {
  page: 1,
  pageSize: 12,
  totalPages: 1,
  category: "",
  q: "",
  categories: [],
  cart: JSON.parse(localStorage.getItem("sme_cart") || "[]"),
  products: {},
};

document.getElementById("logout-link").addEventListener("click", (e) => { e.preventDefault(); logout(); });

/* -------- product loading -------- */
async function loadProducts() {
  const params = new URLSearchParams({
    page: state.page, page_size: state.pageSize, sort: "name",
  });
  if (state.category) params.set("category", state.category);
  if (state.q) params.set("q", state.q);
  const data = await apiGet(`/products?${params.toString()}`);
  state.categories = data.categories;
  state.totalPages = Math.max(1, Math.ceil(data.total / state.pageSize));
  data.items.forEach(p => (state.products[p.id] = p));
  renderCategoryRail();
  renderProductGrid(data.items);
  document.getElementById("page-indicator").textContent = `Page ${state.page} of ${state.totalPages}`;
}

function renderCategoryRail() {
  const rail = document.getElementById("category-rail");
  const chips = ["All", ...state.categories];
  rail.innerHTML = chips.map(c => {
    const value = c === "All" ? "" : c;
    const active = state.category === value ? "active" : "";
    return `<div class="category-chip ${active}" data-cat="${escapeHtml(value)}">${CATEGORY_ICONS[c] || "🛍️"} ${c}</div>`;
  }).join("");
  rail.querySelectorAll(".category-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      state.category = chip.dataset.cat;
      state.page = 1;
      loadProducts();
    });
  });
}

function renderProductGrid(items) {
  const grid = document.getElementById("product-grid");
  if (!items.length) {
    grid.innerHTML = `<div class="empty-state">No products match your search.</div>`;
    return;
  }
  grid.innerHTML = items.map(p => {
    const inCart = state.cart.find(c => c.product_id === p.id);
    const qty = inCart ? inCart.qty : 0;
    return `
    <div class="product-card">
      <div class="product-thumb">${CATEGORY_ICONS[p.category] || "🛍️"}</div>
      <div class="product-name">${escapeHtml(p.name)}</div>
      <div class="product-meta">${p.category} · ⭐ ${p.rating} · ${p.stock} in stock</div>
      <div class="product-price-row">
        <div class="product-price">${formatCurrency(p.price)}</div>
        <div class="qty-stepper" data-id="${p.id}">
          <button class="qty-minus">−</button>
          <span class="qty-val">${qty}</span>
          <button class="qty-plus">+</button>
        </div>
      </div>
    </div>`;
  }).join("");

  grid.querySelectorAll(".qty-stepper").forEach(stepper => {
    const id = parseInt(stepper.dataset.id, 10);
    stepper.querySelector(".qty-plus").addEventListener("click", () => changeQty(id, 1));
    stepper.querySelector(".qty-minus").addEventListener("click", () => changeQty(id, -1));
  });
}

function changeQty(productId, delta) {
  const product = state.products[productId];
  let item = state.cart.find(c => c.product_id === productId);
  if (!item && delta > 0) {
    item = { product_id: productId, qty: 0, name: product.name, price: product.price };
    state.cart.push(item);
  }
  if (!item) return;
  item.qty = Math.max(0, Math.min((product ? product.stock : 999), item.qty + delta));
  state.cart = state.cart.filter(c => c.qty > 0);
  persistCart();
  loadProducts();
  updateCartBadge();
}

function persistCart() {
  localStorage.setItem("sme_cart", JSON.stringify(state.cart));
}

/* -------- search & pagination -------- */
let searchTimer;
document.getElementById("store-search").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.q = e.target.value;
    state.page = 1;
    loadProducts();
  }, 250);
});
document.getElementById("prev-page").addEventListener("click", () => {
  if (state.page > 1) { state.page--; loadProducts(); }
});
document.getElementById("next-page").addEventListener("click", () => {
  if (state.page < state.totalPages) { state.page++; loadProducts(); }
});

/* -------- cart drawer -------- */
const drawer = document.getElementById("cart-drawer");
const overlay = document.getElementById("overlay");

function openCart() {
  renderCartDrawer();
  drawer.classList.add("open");
  overlay.classList.add("show");
}
function closeCart() {
  drawer.classList.remove("open");
  overlay.classList.remove("show");
}
document.getElementById("nav-cart").addEventListener("click", (e) => { e.preventDefault(); openCart(); });
document.getElementById("close-cart").addEventListener("click", closeCart);
overlay.addEventListener("click", closeCart);

function cartTotals() {
  const subtotal = state.cart.reduce((s, c) => s + c.price * c.qty, 0);
  const tax = subtotal * 0.05;
  return { subtotal, tax, total: subtotal + tax };
}

function renderCartDrawer() {
  const itemsEl = document.getElementById("cart-items");
  if (!state.cart.length) {
    itemsEl.innerHTML = `<div class="empty-state">Your cart is empty. Add something tasty!</div>`;
  } else {
    itemsEl.innerHTML = state.cart.map(c => `
      <div class="cart-item">
        <div>
          <div style="font-weight:600;">${escapeHtml(c.name)}</div>
          <div class="muted" style="font-size:11px;">${c.qty} × ${formatCurrency(c.price)}</div>
        </div>
        <div>${formatCurrency(c.qty * c.price)}</div>
      </div>`).join("");
  }
  const { subtotal, tax, total } = cartTotals();
  document.getElementById("cart-subtotal").textContent = formatCurrency(subtotal);
  document.getElementById("cart-tax").textContent = formatCurrency(tax);
  document.getElementById("cart-total").textContent = formatCurrency(total);
  updateCartBadge();
}

function updateCartBadge() {
  const count = state.cart.reduce((s, c) => s + c.qty, 0);
  const badge = document.getElementById("cart-count");
  badge.textContent = count;
  badge.classList.toggle("hidden", count === 0);
}

/* -------- checkout -------- */
document.getElementById("checkout-btn").addEventListener("click", async () => {
  if (!state.cart.length) { showToast("Your cart is empty.", "error"); return; }
  try {
    const res = await apiPost("/checkout", {
      customer_id: 1,
      cart: state.cart.map(c => ({ product_id: c.product_id, qty: c.qty })),
    });
    showInvoice(res.invoice);
    state.cart = [];
    persistCart();
    updateCartBadge();
    closeCart();
    loadProducts();
  } catch (e) {
    showToast(e.message, "error");
  }
});

function showInvoice(invoice) {
  const box = document.getElementById("invoice-content");
  box.innerHTML = `
    <div style="text-align:center;font-weight:700;">SME ANCHOR MART</div>
    <div style="text-align:center;" class="muted">Invoice #${invoice.id}</div>
    <hr/>
    ${invoice.items.map(i => `<div class="line"><span>${escapeHtml(i.name)} ×${i.qty}</span><span>₹${(i.unit_price * i.qty).toFixed(2)}</span></div>`).join("")}
    <hr/>
    <div class="line"><span>Subtotal</span><span>₹${invoice.subtotal.toFixed(2)}</span></div>
    <div class="line"><span>Tax</span><span>₹${invoice.tax.toFixed(2)}</span></div>
    <div class="line" style="font-weight:700;"><span>TOTAL</span><span>₹${invoice.total.toFixed(2)}</span></div>
    <hr/>
    <div style="text-align:center;">Thank you for shopping with us.</div>
  `;
  document.getElementById("invoice-modal").classList.add("show");
}
document.getElementById("invoice-close").addEventListener("click", () => {
  document.getElementById("invoice-modal").classList.remove("show");
});

/* -------- orders modal (placeholder) -------- */
document.getElementById("nav-orders").addEventListener("click", (e) => {
  e.preventDefault();
  document.getElementById("orders-modal").classList.add("show");
});
document.getElementById("orders-close").addEventListener("click", () => {
  document.getElementById("orders-modal").classList.remove("show");
});

/* -------- init -------- */
updateCartBadge();
loadProducts();
