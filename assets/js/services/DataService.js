// DataService.js — robust CSV + helpers + price history
class DataService {
  constructor(csvPath = "../api/RFP.csv") {
    this.csvPath = csvPath;
    this.data = [];
    this.photos = [
      "https://images.unsplash.com/photo-1559329146-807aff9ff1fb?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
      "https://images.unsplash.com/photo-1654506012740-09321c969dc2?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
      "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
      "https://images.unsplash.com/photo-1590490360182-c33d57733427?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080",
      "https://images.unsplash.com/photo-1560185008-b033106afce3?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&q=80&w=1080"
    ];
    this.fallbackPhoto = this.photos[2];
  }

  // CSV parser that respects quotes + commas
  parseCSV(text) {
    const out = [];
    let row = [], cur = "", inQ = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i], n = text[i + 1];
      if (c === '"' && n === '"') { cur += '"'; i++; continue; } // escaped quote
      if (c === '"') { inQ = !inQ; continue; }
      if (c === ',' && !inQ) { row.push(cur); cur = ""; continue; }
      if ((c === '\n' || c === '\r') && !inQ) {
        if (cur !== "" || row.length) { row.push(cur); out.push(row); row = []; cur = ""; }
        continue;
      }
      cur += c;
    }
    if (cur !== "" || row.length) { row.push(cur); out.push(row); }
    return out;
  }

  cleanHeader(h) {
    return String(h || "")
      .replace(/^\uFEFF/, "") // strip BOM
      .replace(/\s+/g, " ")   // normalize inner spaces
      .trim()
      .replace(/^"|"$/g, ""); // strip wrapping quotes
  }

  cleanCell(v) {
    return String(v ?? "")
      .trim()
      .replace(/^"|"$/g, ""); // strip wrapping quotes
  }

  async load() {
    const res = await fetch(this.csvPath);
    if (!res.ok) throw new Error(`Failed to fetch CSV: ${res.status}`);
    const raw = await res.text();

    // Normalize line endings
    const text = raw.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
    const rows = this.parseCSV(text);
    if (!rows.length) { this.data = []; return; }

    const headers = rows.shift().map(h => this.cleanHeader(h));
    const idx = (name) => headers.findIndex(h => h.toLowerCase() === name.toLowerCase());

    const h = {
      month: idx("Month"),
      town: idx("Town"),
      flatType: idx("Flat Type"),
      block: idx("Block"),
      street: idx("Street Name"),
      storey: idx("Storey Range"),
      sqm: idx("Floor Area Sqm"),
      model: idx("Flat Model"),
      leaseStart: idx("Lease Commence Date"),
      remaining: idx("Remaining Lease"),
      price: idx("Resale Price"),
    };

    this.data = rows
      .map((r) => {
        const obj = {
          "Month": this.cleanCell(r[h.month]),
          "Town": this.cleanCell(r[h.town]),
          "Flat Type": this.cleanCell(r[h.flatType]),
          "Block": this.cleanCell(r[h.block]),
          "Street Name": this.cleanCell(r[h.street]),
          "Storey Range": this.cleanCell(r[h.storey]),
          "Floor Area Sqm": this.cleanCell(r[h.sqm]),
          "Flat Model": this.cleanCell(r[h.model]),
          "Lease Commence Date": this.cleanCell(r[h.leaseStart]),
          "Remaining Lease": this.cleanCell(r[h.remaining]),
          "Resale Price": this.cleanCell(r[h.price]),
        };

        // derived metrics
        obj._price = this.num(obj["Resale Price"]);
        obj._sqm = this.num(obj["Floor Area Sqm"]);
        obj._sqft = obj._sqm ? Math.round(obj._sqm * 10.7639) : null;
        obj._bed = this.guessBedrooms(obj["Flat Type"]);
        obj._psf = (obj._sqft && obj._price) ? Math.round(obj._price / obj._sqft) : null;
        obj._ym = (obj["Month"] || "").substring(0, 7);

        // deterministic photo by address
        const key = `${obj["Block"]}-${obj["Street Name"]}-${obj["Flat Type"]}`;
        const idx = [...key].reduce((a, ch) => (a + ch.charCodeAt(0)) % this.photos.length, 0);
        obj.image = this.photos[idx] || this.fallbackPhoto;

        return obj;
      })
      // keep only plausible rows (have price and address)
      .filter(o => o._price > 0 && o["Block"] && o["Street Name"]);
  }

  num(v) {
    const n = Number(String(v || "").replace(/[^\d.]/g, ""));
    return Number.isFinite(n) ? n : 0;
  }

  guessBedrooms(flatType = "") {
    const m = flatType.match(/^(\d)/);
    return m ? Number(m[1]) : 3;
  }

  formatCurrency(n) {
    return (n && Number.isFinite(n)) ? "$" + n.toLocaleString("en-SG") : "$0";
  }

  getPriceHistory(rec) {
    const same = this.data.filter(d =>
      d["Block"] === rec["Block"] &&
      d["Street Name"] === rec["Street Name"] &&
      d["Flat Type"] === rec["Flat Type"]
    );
    const byMonth = new Map();
    same.forEach(d => {
      if (!d._ym) return;
      const arr = byMonth.get(d._ym) || [];
      arr.push(d._price);
      byMonth.set(d._ym, arr);
    });
    const list = [...byMonth.entries()].map(([ym, arr]) => ({
      ym,
      price: Math.round(arr.reduce((a,b)=>a+b,0) / arr.length)
    }));
    list.sort((a,b)=> a.ym.localeCompare(b.ym));
    return list.slice(-6);
  }
}

window.DataService = DataService;