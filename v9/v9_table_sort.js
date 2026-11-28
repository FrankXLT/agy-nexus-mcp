/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Multi-Column Analytics Table Sorting, Age Parsing & Accessible Headers */
(() => {
  const V9 = (window.AgyV9 = window.AgyV9 || {});
  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });

  const DEFAULT_SORTS = {
    projects: { key: "steps", dir: "desc" },
    sessions: { key: "steps", dir: "desc" },
    models: { key: "share", dir: "desc" },
    subagents: { key: "share", dir: "desc" },
  };

  function ensureSortState() {
    const st = (V9.state = V9.state || {});
    if (!st.tableSort || typeof st.tableSort !== "object") st.tableSort = {};
    for (const [tid, def] of Object.entries(DEFAULT_SORTS)) {
      if (!st.tableSort[tid]) st.tableSort[tid] = { key: def.key, dir: def.dir };
    }
    return st.tableSort;
  }

  function getSort(tableId) {
    const map = ensureSortState();
    return map[tableId] || { key: "steps", dir: "desc" };
  }

  function setSort(tableId, colKey, defaultDir) {
    const map = ensureSortState();
    const cur = map[tableId] || DEFAULT_SORTS[tableId] || { key: colKey, dir: "desc" };
    if (cur.key === colKey) {
      cur.dir = cur.dir === "asc" ? "desc" : "asc";
    } else {
      cur.key = colKey;
      cur.dir = defaultDir === "asc" ? "asc" : "desc";
    }
    map[tableId] = cur;
    return cur;
  }

  function parseRelativeAgeSeconds(raw) {
    const s = String(raw || "").trim().toLowerCase();
    if (!s) return null;
    if (s === "just now" || s === "now") return 0;
    const m = /(\d+(?:\.\d+)?)\s*(s|sec|secs|m|min|mins|h|hr|hrs|d|day|days|w|wk|wks|mo|y)\b/.exec(s);
    if (!m) return null;
    const n = Number(m[1]);
    const u = m[2];
    if (!Number.isFinite(n)) return null;
    if (u.startsWith("s")) return n;
    if (u === "mo") return n * 2592000;
    if (u.startsWith("m")) return n * 60;
    if (u.startsWith("h")) return n * 3600;
    if (u.startsWith("d")) return n * 86400;
    if (u.startsWith("w")) return n * 604800;
    if (u === "y") return n * 31536000;
    return null;
  }

  function formatAgeFromTs(ts) {
    const t = Number(ts || 0);
    if (!Number.isFinite(t) || t <= 0) return "";
    const diff = Math.max(0, Math.floor(Date.now() / 1000 - t));
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  function recencyEpoch(item, nowRef) {
    if (!item || typeof item !== "object") return 0;
    const rawTs = Number(item.last_updated_ts || 0);
    if (Number.isFinite(rawTs) && rawTs > 0) return rawTs;
    if (item.last_updated) {
      const ms = Date.parse(item.last_updated);
      if (Number.isFinite(ms) && ms > 0) return ms / 1000;
    }
    if (Array.isArray(item.sessions) && item.sessions.length) {
      let best = 0;
      for (const s of item.sessions) {
        const stTs = recencyEpoch(s, nowRef);
        if (stTs > best) best = stTs;
      }
      if (best > 0) return best;
    }
    const ageSec = parseRelativeAgeSeconds(item.relative_age);
    if (ageSec != null) return Math.max(1, (nowRef || Date.now() / 1000) - ageSec);
    return 0;
  }

  function getAgeLabel(item) {
    if (!item || typeof item !== "object") return "—";
    if (item.relative_age) return String(item.relative_age);
    const ts = recencyEpoch(item, Date.now() / 1000);
    return formatAgeFromTs(ts) || "recent";
  }

  function statusRank(item) {
    const st = String((item && item.status) || "").trim().toUpperCase();
    if (st === "STALLED_WAITING_APPROVAL") return 5;
    if ((item && item.is_running) || st === "RUNNING") return 4;
    if (st === "IDLE" || !st) return 3;
    if (st === "COMPLETED") return 2;
    if (st === "RETIRED") return 1;
    return 0;
  }

  function sortItems(items, tableId, extractorMap) {
    const list = Array.isArray(items) ? items.slice() : [];
    const cur = getSort(tableId);
    const spec = (extractorMap && extractorMap[cur.key]) || {};
    const getVal = typeof spec === "function" ? spec : spec.get;
    if (typeof getVal !== "function") return list;
    const isText = spec.type === "text";
    const factor = cur.dir === "asc" ? 1 : -1;
    const indexed = list.map((item, idx) => ({ item, idx, val: getVal(item) }));
    indexed.sort((a, b) => {
      let cmp = 0;
      if (isText) {
        cmp = collator.compare(String(a.val || ""), String(b.val || ""));
      } else {
        const na = Number(a.val || 0);
        const nb = Number(b.val || 0);
        cmp = (Number.isFinite(na) ? na : 0) - (Number.isFinite(nb) ? nb : 0);
      }
      if (cmp !== 0) return cmp * factor;
      return a.idx - b.idx;
    });
    return indexed.map((entry) => entry.item);
  }

  function thHtml(tableId, colKey, label, opts) {
    const o = opts || {};
    const cur = getSort(tableId);
    const isActive = cur.key === colKey;
    const ariaSort = isActive ? (cur.dir === "asc" ? "ascending" : "descending") : "";
    const defDir = o.defaultDir || (o.type === "text" ? "asc" : "desc");
    const clsAttr = o.cls ? ` class="${V9.escHtml(o.cls)}"` : "";
    const ariaAttr = ariaSort ? ` aria-sort="${ariaSort}"` : "";
    const labelHtml = o.rawLabel ? label : V9.escHtml(label);
    return `<th scope="col"${clsAttr}${ariaAttr}><button type="button" class="v9-th-sort" data-sort-table="${V9.escHtml(tableId)}" data-sort-key="${V9.escHtml(colKey)}" data-default-dir="${V9.escHtml(defDir)}"><span class="v9-th-lbl">${labelHtml}</span><svg class="v9-sort-ind" width="10" height="10" viewBox="0 0 12 12" fill="none" aria-hidden="true"><path class="v9-sort-up" d="M3 4.8L6 2L9 4.8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path class="v9-sort-dn" d="M3 7.2L6 10L9 7.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button></th>`;
  }

  function syncTheadSort(thead, tableId) {
    if (!thead) return;
    const cur = getSort(tableId);
    thead.querySelectorAll("th").forEach((th) => {
      const btn = th.querySelector(`[data-sort-table="${tableId}"]`);
      if (!btn) return;
      const key = btn.getAttribute("data-sort-key");
      if (key === cur.key) th.setAttribute("aria-sort", cur.dir === "asc" ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    });
  }

  function announceSort(label, dir, rowCount) {
    const el = document.getElementById("v9SortStatus");
    if (!el) return;
    const dirWord = dir === "asc" ? "ascending" : "descending";
    el.textContent = `Sorted by ${String(label || "").replace(/\s+/g, " ").trim()}, ${dirWord}${rowCount != null ? `, ${rowCount} rows` : ""}`;
  }

  const sortHandlers = new WeakMap();

  function bindSortHeaders(root, tableId, onSort, rowCountFn) {
    if (!root) return;
    sortHandlers.set(root, { tableId, onSort, rowCountFn });
    if (root.dataset.v9SortBound === tableId) return;
    root.dataset.v9SortBound = tableId;
    root.addEventListener("click", (ev) => {
      const reg = sortHandlers.get(root);
      if (!reg) return;
      const btn = ev.target && ev.target.closest ? ev.target.closest(`button[data-sort-table="${reg.tableId}"]`) : null;
      if (!btn || !root.contains(btn)) return;
      ev.stopPropagation();
      const key = btn.getAttribute("data-sort-key") || "";
      const defDir = btn.getAttribute("data-default-dir") || "desc";
      const next = setSort(reg.tableId, key, defDir);
      const lbl = btn.querySelector(".v9-th-lbl")?.textContent || key;
      if (typeof reg.onSort === "function") reg.onSort(next, key);
      const count = typeof reg.rowCountFn === "function" ? reg.rowCountFn() : null;
      announceSort(lbl, next.dir, count);
    });
  }

  ensureSortState();
  V9.TableSort = {
    DEFAULT_SORTS,
    getSort,
    setSort,
    parseRelativeAgeSeconds,
    recencyEpoch,
    getAgeLabel,
    statusRank,
    sortItems,
    thHtml,
    syncTheadSort,
    bindSortHeaders,
  };
})();
