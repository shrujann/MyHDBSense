/* Filters.js
 * Simple component controller for the HDB search form:
 * - serializes form -> dispatches `filters:submit`
 * - handles reset -> dispatches `filters:reset`
 * - wires up Expand/Collapse for advanced filters (Bootstrap Collapse)
 */

class Filters {
  constructor(rootEl) {
    // Allow passing the include wrapper or the form container
    this.root = rootEl;
    this.form = this.root.querySelector("#searchFilters");
    if (!this.form) return;

    this._bindSubmit();
    this._bindReset();
    this._initExpandCollapse(); // <-- moved here so it always runs
  }

  _bindSubmit() {
    this.form.addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(this.form);
      const payload = {};

      for (const [k, v] of fd.entries()) {
        if (payload[k] !== undefined) {
          // normalize to array for multi-select fields like flatModel[]
          if (!Array.isArray(payload[k])) payload[k] = [payload[k]];
          payload[k].push(v);
        } else {
          payload[k] = v;
        }
      }

      this.root.dispatchEvent(
        new CustomEvent("filters:submit", { detail: payload, bubbles: true })
      );
    });
  }

  _bindReset() {
    this.form.addEventListener("reset", () => {
      // allow the browser to clear UI first, then notify
      setTimeout(() => {
        this.root.dispatchEvent(new CustomEvent("filters:reset", { bubbles: true }));
      }, 0);
    });
  }

  _initExpandCollapse() {
    const adv = this.root.querySelector('[data-role="advanced"]');
    const btn = this.root.querySelector('[data-role="expand-toggle"]');
    if (!adv || !btn || typeof bootstrap === "undefined") return;

    // Ensure a unique id per instance so multiple components won't collide
    const uid = "adv-" + Math.random().toString(36).slice(2, 8);
    adv.id = uid;
    btn.setAttribute("aria-controls", uid);

    // Create a Bootstrap Collapse instance (start collapsed)
    const collapse = new bootstrap.Collapse(adv, { toggle: false });

    // Clicking the button toggles the collapse
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      if (adv.classList.contains("show")) {
        collapse.hide();
      } else {
        collapse.show();
      }
    });

    // Keep button text in sync
    adv.addEventListener("shown.bs.collapse", () => (btn.textContent = "Collapse"));
    adv.addEventListener("hidden.bs.collapse", () => (btn.textContent = "Expand"));
  }
}

window.Filters = Filters;