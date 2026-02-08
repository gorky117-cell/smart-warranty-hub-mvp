/**
 * Warranty Dropdown - Shared component for all dashboards
 * Include this script in any dashboard to add multi-warranty support
 */
(function () {
    // Wait for DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        injectDropdownUI();
        loadWarranties();
    }

    function injectDropdownUI() {
        // Check if already injected
        if (document.getElementById('warranty-selector-card')) return;

        const card = document.createElement('div');
        card.id = 'warranty-selector-card';
        card.className = 'card';
        card.style.cssText = 'background:#fff; border-radius:14px; padding:16px; box-shadow:0 4px 12px rgba(0,0,0,0.08); margin-bottom:16px; border:1px solid #e5e7eb;';
        card.innerHTML = `
      <h3 style="margin:0 0 12px 0; font-size:16px; font-weight:700;">📦 Select Warranty</h3>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
        <div>
          <label style="display:block; font-size:12px; color:#6b7280; margin-bottom:4px;">Saved Warranties</label>
          <select id="warrantyDropdown" style="width:100%; padding:10px; border:1px solid #e5e7eb; border-radius:8px; font-size:14px;">
            <option value="">-- Loading... --</option>
          </select>
        </div>
        <div>
          <label style="display:block; font-size:12px; color:#6b7280; margin-bottom:4px;">Current ID</label>
          <input id="warrantyId" placeholder="wty_xxx" style="width:100%; padding:10px; border:1px solid #e5e7eb; border-radius:8px; font-size:14px;" />
        </div>
      </div>
    `;

        // Insert at top of container or first card
        const container = document.querySelector('.container');
        const firstCard = container ? container.querySelector('.card') : document.querySelector('.card');
        if (firstCard && firstCard.parentNode) {
            firstCard.parentNode.insertBefore(card, firstCard);
        } else if (container) {
            container.insertBefore(card, container.firstChild);
        } else {
            document.body.insertBefore(card, document.body.firstChild);
        }

        // Add change listener
        const dropdown = document.getElementById('warrantyDropdown');
        if (dropdown) {
            dropdown.addEventListener('change', function () {
                const input = document.getElementById('warrantyId');
                if (input && this.value) {
                    input.value = this.value;
                }
            });
        }
    }

    async function loadWarranties() {
        const dropdown = document.getElementById('warrantyDropdown');
        if (!dropdown) return;

        try {
            const res = await fetch('/warranties/list');
            const data = await res.json();
            const warranties = data.warranties || [];

            dropdown.innerHTML = '<option value="">-- Select (' + warranties.length + ' saved) --</option>';
            warranties.forEach(function (w) {
                const label = w.brand || w.product_name || 'Unknown';
                const expiry = w.expiry_date ? new Date(w.expiry_date).toLocaleDateString() : 'No expiry';
                const opt = document.createElement('option');
                opt.value = w.id;
                opt.textContent = label + ' - ' + (w.model_code || w.id) + ' (Exp: ' + expiry + ')';
                dropdown.appendChild(opt);
            });
        } catch (e) {
            dropdown.innerHTML = '<option value="">-- Error loading --</option>';
            console.error('loadWarranties error', e);
        }
    }

    // Expose reload function globally
    window.reloadWarrantyDropdown = loadWarranties;
})();
