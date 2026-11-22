/* SIMRS Lab - interaksi ringan (tanpa framework) */
(function () {
  "use strict";

  // ---- Flag otomatis saat mengetik hasil ---------------------------------
  function num(v) { return parseFloat(String(v).replace(",", ".")); }
  function flagOf(el) {
    var v = num(el.value);
    if (el.value.trim() === "" || isNaN(v)) return null;
    var d = el.dataset, lo = d.min === "" ? null : +d.min, hi = d.max === "" ? null : +d.max;
    var kl = d.kmin === "" ? null : +d.kmin, kh = d.kmax === "" ? null : +d.kmax;
    if (kl !== null && v < kl) return "LL";
    if (kh !== null && v > kh) return "HH";
    if (lo !== null && v < lo) return "L";
    if (hi !== null && v > hi) return "H";
    return "N";
  }
  var FL = { N: ["–", "fl-n"], H: ["H", "fl-h"], L: ["L", "fl-l"], HH: ["HH", "fl-c"], LL: ["LL", "fl-c"], A: ["A", "fl-h"] };
  function paint(el, flag) {
    var cell = document.getElementById("flag_" + el.dataset.pid);
    if (!cell) return;
    el.classList.remove("abn", "low");
    if (!flag) { cell.innerHTML = ""; return; }
    cell.innerHTML = '<span class="fl ' + FL[flag][1] + '">' + FL[flag][0] + "</span>";
    if (flag === "H" || flag === "HH" || flag === "LL" || flag === "A") el.classList.add("abn");
    if (flag === "L") el.classList.add("low");
  }
  document.querySelectorAll("input.val[data-pid]").forEach(function (el) {
    el.addEventListener("input", function () {
      paint(el, flagOf(el));
      var m = document.getElementById("dev_" + el.dataset.pid); if (m) m.remove();
      var h = document.getElementById("alat_" + el.dataset.pid); if (h) h.value = "";
    });
    paint(el, flagOf(el));
  });
  document.querySelectorAll("select.val[data-pid]").forEach(function (el) {
    function upd() {
      var cell = document.getElementById("flag_" + el.dataset.pid);
      if (!el.value) { cell.innerHTML = ""; el.classList.remove("abn"); return; }
      var bad = el.value !== el.dataset.normal;
      cell.innerHTML = bad ? '<span class="fl fl-h">A</span>' : '<span class="fl fl-n">–</span>';
      el.classList.toggle("abn", bad);
    }
    el.addEventListener("change", upd); upd();
  });

  // ---- Ambil hasil dari alat (simulasi LIS) --------------------------------
  var btn = document.getElementById("btn-alat");
  if (btn) btn.addEventListener("click", function () {
    btn.disabled = true;
    fetch(btn.dataset.url).then(function (r) { return r.json(); }).then(function (data) {
      Object.keys(data).forEach(function (pid) {
        var el = document.getElementById("val_" + pid); if (!el) return;
        el.value = el.tagName === "INPUT" ? String(data[pid]).replace(".", ",") : data[pid];
        el.dispatchEvent(new Event(el.tagName === "INPUT" ? "input" : "change"));
        var h = document.getElementById("alat_" + pid); if (h) h.value = "1";
        var c = document.getElementById("flag_" + pid);
        if (c && !document.getElementById("dev_" + pid)) c.insertAdjacentHTML("beforeend", '<span class="dev" id="dev_' + pid + '">alat</span>');
      });
    }).finally(function () { btn.disabled = false; });
  });

  // ---- Form order baru: total tarif + autocomplete pasien --------------------
  var totalEl = document.getElementById("total-tarif");
  if (totalEl) {
    var calc = function () {
      var t = 0, n = 0;
      document.querySelectorAll('input[name="test_id"]:checked').forEach(function (c) { t += +c.dataset.tarif; n++; });
      totalEl.textContent = "Rp " + t.toLocaleString("id-ID");
      document.getElementById("jumlah-tes").textContent = n;
    };
    document.querySelectorAll('input[name="test_id"]').forEach(function (c) { c.addEventListener("change", calc); });
    calc();
  }
  var inp = document.getElementById("pasien-q");
  if (inp) {
    var box = document.getElementById("pasien-ac"), hid = document.getElementById("patient_id"), tm;
    var info = document.getElementById("pasien-info");
    inp.addEventListener("input", function () {
      clearTimeout(tm); hid.value = "";
      if (inp.value.trim().length < 1) { box.hidden = true; return; }
      tm = setTimeout(function () {
        fetch("/api/patients?q=" + encodeURIComponent(inp.value)).then(function (r) { return r.json(); }).then(function (rows) {
          box.innerHTML = "";
          if (!rows.length) { box.innerHTML = '<div class="p-3 sub">Tidak ada pasien. <a href="/patients/baru">Daftarkan pasien baru</a></div>'; }
          rows.forEach(function (p) {
            var b = document.createElement("button"); b.type = "button";
            b.innerHTML = "<b></b> <span class='sub'></span>";
            b.querySelector("b").textContent = p.nama;
            b.querySelector("span").textContent = p.no_rm + " · " + (p.jenis_kelamin === "L" ? "Laki-laki" : "Perempuan") + ", " + p.umur + " th";
            b.onclick = function () { hid.value = p.id; inp.value = p.nama + " (" + p.no_rm + ")"; box.hidden = true; if (info) info.textContent = ""; };
            box.appendChild(b);
          });
          box.hidden = false;
        });
      }, 180);
    });
    document.addEventListener("click", function (e) { if (!box.contains(e.target) && e.target !== inp) box.hidden = true; });
  }

  // ---- Barcode ---------------------------------------------------------------
  if (window.JsBarcode) document.querySelectorAll("svg.barcode").forEach(function (s) {
    JsBarcode(s, s.dataset.code, { format: "CODE128", height: 48, displayValue: true, fontSize: 13, margin: 0 });
  });

  // ---- Konfirmasi ------------------------------------------------------------
  document.querySelectorAll("[data-confirm]").forEach(function (f) {
    f.addEventListener("submit", function (e) { if (!confirm(f.dataset.confirm)) e.preventDefault(); });
  });
})();
