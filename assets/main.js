// ================== includes (navbar, filters, etc.) ==================
async function loadIncludes() {
  var slots = Array.prototype.slice.call(document.querySelectorAll("[data-include]"));
  for (var i = 0; i < slots.length; i++) {
    var el = slots[i];
    var src = el.getAttribute("data-include");
    try {
      var res = await fetch(src, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      el.innerHTML = await res.text();

      // Mount filters component when requested (if present)
      var comp = el.getAttribute("data-component");
      if (comp === "filters" && typeof Filters === "function") {
        try { new Filters(el); } catch (e) { /* ignore */ }
      }
    } catch (e) {
      console.error("Failed to include:", src, e);
      el.innerHTML = '<div class="alert alert-warning small">Failed to load ' + src + '</div>';
    }
  }
}

// ================== mock database (users + CSV mirror) ==================
var Users = {
  jsonKey: "mhs_users",
  csvKey:  "mhs_users_csv",

  list: function () {
    try { return JSON.parse(localStorage.getItem(this.jsonKey) || "[]"); }
    catch (e) { return []; }
  },

  save: function (list) {
    localStorage.setItem(this.jsonKey, JSON.stringify(list));
    this._updateCSV(list);
  },

  add: function (email, password) {
    var list = this.list();
    list.push({ email: email, password: password, created_at: new Date().toISOString() });
    this.save(list);
  },

  exists: function (email) {
    var e = (email || "").toLowerCase();
    var list = this.list();
    for (var i = 0; i < list.length; i++) {
      if ((list[i].email || "").toLowerCase() === e) return true;
    }
    return false;
  },

  find: function (email, password) {
    var e = (email || "").toLowerCase();
    var list = this.list();
    for (var i = 0; i < list.length; i++) {
      var u = list[i];
      if ((u.email || "").toLowerCase() === e && u.password === password) return u;
    }
    return null;
  },

  _updateCSV: function (list) {
    function esc(x){ return '"' + String(x == null ? "" : x).replace(/"/g,'""') + '"'; }
    var rows = [["email","password","created_at"]]
      .concat(list.map(function(u){ return [u.email, u.password, u.created_at]; }));
    var csv = rows.map(function(r){ return r.map(esc).join(","); }).join("\n");
    localStorage.setItem(this.csvKey, csv);
  },

  getCSV: function () {
    return localStorage.getItem(this.csvKey) || "email,password,created_at\n";
  }
};

// Optional helper (you can remove if not used anywhere)
window.exportUsersCSV = function exportUsersCSV() {
  var csv = Users.getCSV();
  var blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  var url = URL.createObjectURL(blob);
  var a = document.createElement("a");
  a.href = url; a.download = "users.csv";
  document.body.appendChild(a); a.click();
  URL.revokeObjectURL(url); a.remove();
};

// ================== session + navbar toggle ==================
var Session = {
  key: "mhs_user",
  get: function () { try { return JSON.parse(localStorage.getItem(this.key)); } catch (e) { return null; } },
  set: function (u) { localStorage.setItem(this.key, JSON.stringify(u)); },
  clear: function () { localStorage.removeItem(this.key); }
};

function refreshNavbarAuth() {
  var user = Session.get();
  var btnLogin = document.getElementById("btnOpenLogin");
  var userDD   = document.getElementById("navUserDropdown");
  var emailEl  = document.getElementById("navUserEmail");

  if (!btnLogin || !userDD) return;

  if (user && user.email) {
    btnLogin.classList.add("d-none");
    userDD.classList.remove("d-none");
    if (emailEl) emailEl.textContent = user.email;
  } else {
    userDD.classList.add("d-none");
    btnLogin.classList.remove("d-none");
  }
}

function highlightActiveNav() {
  var current = location.pathname.split("/").pop() || "index.html";
  var links = document.querySelectorAll(".nav-link[href]");
  for (var i = 0; i < links.length; i++) {
    var a = links[i];
    var end = a.getAttribute("href").split("/").pop();
    if (end === current) a.classList.add("active");
  }
}

// ================== ensure login modal exists on all pages ==================
async function ensureAuthModal() {
  if (document.getElementById("authModal")) return;

  var paths = [
    "../assets/components/loginmodal.html",
    "assets/components/loginmodal.html",
    "./assets/components/loginmodal.html"
  ];

  for (var i = 0; i < paths.length; i++) {
    var p = paths[i];
    try {
      var res = await fetch(p, { cache: "no-store" });
      if (!res.ok) continue;
      var html = await res.text();
      var wrap = document.createElement("div");
      wrap.innerHTML = html.trim();
      var el = wrap.firstElementChild;
      if (el) { document.body.appendChild(el); return; }
    } catch (e) { /* try next path */ }
  }
  console.warn("authModal not injected (no path matched).");
}

// ================== toggle Sign In <-> Register (delegated) ==================
function bindAuthToggles() {
  document.addEventListener("click", function (e) {
    var sw = e.target.closest ? e.target.closest("[data-switch]") : null;
    if (!sw) return;
    e.preventDefault();

    var login = document.getElementById("loginForm");
    var reg   = document.getElementById("registerForm");
    if (!login || !reg) return;

    var go = sw.getAttribute("data-switch");
    var alertBox = document.getElementById("authAlert");
    if (alertBox) alertBox.classList.add("d-none");

    if (go === "register") {
      login.classList.add("d-none");
      reg.classList.remove("d-none");
    } else if (go === "login") {
      reg.classList.add("d-none");
      login.classList.remove("d-none");
    }
  });
}

// ================== auth handlers (login/register/logout) ==================
function bindAuthHandlers() {
  if (window.__mhsAuthBound) return;
  window.__mhsAuthBound = true;

  document.addEventListener("submit", function (e) {
    var form = e.target;

    // Sign In
    if (form && form.id === "loginForm") {
      e.preventDefault();
      var email = ((document.getElementById("loginEmail") || {}).value || "").trim();
      var pass  = ((document.getElementById("loginPassword") || {}).value || "").trim();
      if (!email || !pass) return showAuthError("Please enter both email and password.");

      var user = Users.find(email, pass);
      if (!user) return showAuthError("Invalid email or password.");

      Session.set({ email: email });
      hideAuthError();
      refreshNavbarAuth();
      closeAuthModal();
      return;
    }

    // Register
    if (form && form.id === "registerForm") {
      e.preventDefault();
      var email = ((document.getElementById("regEmail") || {}).value || "").trim();
      var p1    = ((document.getElementById("regPassword") || {}).value || "").trim();
      var p2    = ((document.getElementById("regPassword2") || {}).value || "").trim();

      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return showAuthError("Please enter a valid email address.");
      if (p1.length < 8) return showAuthError("Password must be at least 8 characters.");
      if (!/[A-Za-z]/.test(p1) || !/[0-9]/.test(p1)) return showAuthError("Password must include letters and numbers.");
      if (p1 !== p2) return showAuthError("Passwords do not match.");
      if (Users.exists(email)) return showAuthError("Account already exists. Please sign in.");

      Users.add(email, p1);          // persist (JSON + CSV mirror)
      Session.set({ email: email }); // auto sign-in
      hideAuthError();
      refreshNavbarAuth();
      closeAuthModal();
      return;
    }
  });

  document.addEventListener("click", function (e) {
    var logout = e.target.closest ? e.target.closest("[data-action='logout']") : null;
    if (logout) { Session.clear(); refreshNavbarAuth(); }
  });
}

function showAuthError(msg) {
  var box = document.getElementById("authAlert");
  if (box) { box.textContent = msg; box.classList.remove("d-none"); }
}
function hideAuthError() {
  var box = document.getElementById("authAlert");
  if (box) box.classList.add("d-none");
}
function closeAuthModal() {
  var el = document.getElementById("authModal");
  try {
    if (el && window.bootstrap && bootstrap.Modal) {
      bootstrap.Modal.getOrCreateInstance(el).hide();
    } else if (el) {
      // Fallback: just hide via class if bootstrap not present
      el.classList.remove("show");
      el.style.display = "none";
      document.body.classList.remove("modal-open");
      var backdrops = document.querySelectorAll(".modal-backdrop");
      for (var i = 0; i < backdrops.length; i++) backdrops[i].remove();
    }
  } catch (e) {
    console.warn("closeAuthModal fallback", e);
  }
}

// ================== boot ==================
document.addEventListener("DOMContentLoaded", async function () {
  await loadIncludes();       // navbar/search partials
  await ensureAuthModal();    // inject login modal if missing
  bindAuthToggles();          // Register now! <-> Back to Sign In
  bindAuthHandlers();         // login/register/CSV/session handlers
  refreshNavbarAuth();        // show Sign In or Profile
  highlightActiveNav();

  // Build CSV mirror if missing (one-time)
  if (!localStorage.getItem(Users.csvKey)) {
    Users._updateCSV(Users.list());
  }
});