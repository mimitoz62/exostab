// Sort the catalog table by clicking a column header, and filter rows by system name.
// Works with Material for MkDocs instant navigation (document$) and with plain page loads.
(function () {
  function setup() {
    var table = document.getElementById("catalog-table");
    if (!table || table.dataset.ready) return;
    table.dataset.ready = "1";
    var tbody = table.tBodies[0];
    var headers = table.tHead.rows[0].cells;
    Array.prototype.forEach.call(headers, function (th, col) {
      th.setAttribute("role", "button");
      th.setAttribute("tabindex", "0");
      th.setAttribute("aria-sort", "none");
      function sort() {
        var asc = th.getAttribute("aria-sort") !== "ascending";
        Array.prototype.forEach.call(headers, function (h) { h.setAttribute("aria-sort", "none"); });
        th.setAttribute("aria-sort", asc ? "ascending" : "descending");
        var rows = Array.prototype.slice.call(tbody.rows);
        rows.sort(function (a, b) {
          var x = a.cells[col].dataset.sort, y = b.cells[col].dataset.sort;
          var nx = parseFloat(x), ny = parseFloat(y);
          var cmp = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : x.localeCompare(y);
          return asc ? cmp : -cmp;
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      }
      th.addEventListener("click", sort);
      th.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sort(); } });
    });
    var filter = document.getElementById("catalog-filter");
    var none = document.getElementById("catalog-filter-none");
    // Case, spaces and punctuation are ignored, as in `exostab check`: "trappist 1" finds TRAPPIST-1.
    function key(text) { return text.toLowerCase().replace(/[^0-9a-z]+/g, ""); }
    if (filter) {
      filter.addEventListener("input", function () {
        var q = key(filter.value), shown = 0;
        Array.prototype.forEach.call(tbody.rows, function (r) {
          var match = (r.cells[0].textContent + ";" + (r.dataset.names || "")).split(";").some(function (name) {
            return key(name).indexOf(q) !== -1;
          });
          r.style.display = match ? "" : "none";
          if (match) shown += 1;
        });
        if (none) none.hidden = shown > 0;
      });
    }
  }
  if (typeof document$ !== "undefined") { document$.subscribe(setup); } else { document.addEventListener("DOMContentLoaded", setup); }
})();
