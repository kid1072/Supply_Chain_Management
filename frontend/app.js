(function () {
  "use strict";

  const API = window.SupplyAPI;

  const ROLE_LABELS = Object.freeze({
    admin: "系统管理员",
    purchaser: "采购人员",
    warehouse: "仓库人员",
    store: "门店人员",
    manager: "业务主管",
  });

  const ROLE_BACKEND_USERNAMES = Object.freeze({
    admin: "admin",
    purchaser: "buyer",
    warehouse: "warehouse",
    store: "store",
    manager: "manager",
  });

  const ROLE_BACKEND_CODES = Object.freeze({
    admin: ["admin"],
    purchaser: ["buyer", "purchaser"],
    warehouse: ["warehouse_manager", "warehouse"],
    store: ["store_staff", "store"],
    manager: ["manager"],
  });

  const MODULE_DEFINITIONS = Object.freeze({
    dashboard: { label: "首页看板" },
    data: { label: "基础数据录入" },
    warnings: { label: "库存查询与预警" },
    inbound: { label: "采购入库" },
    fulfillment: { label: "门店补货与出库" },
    transactions: { label: "库存流水追溯" },
    recommendations: { label: "智能补货建议" },
    analytics: { label: "统计分析" },
    suppliers: { label: "供应商排行" },
    system: { label: "系统状态" },
  });

  const ROLE_MODULES = Object.freeze({
    admin: [
      "dashboard",
      "data",
      "warnings",
      "inbound",
      "fulfillment",
      "transactions",
      "recommendations",
      "analytics",
      "suppliers",
      "system",
    ],
    purchaser: ["dashboard", "warnings", "inbound", "suppliers", "system"],
    warehouse: ["dashboard", "warnings", "inbound", "fulfillment", "transactions", "system"],
    store: ["dashboard", "fulfillment", "recommendations", "system"],
    manager: [
      "dashboard",
      "warnings",
      "fulfillment",
      "recommendations",
      "analytics",
      "suppliers",
      "system",
    ],
  });

  const ACTION_ROLES = Object.freeze({
    "create-base-data": ["admin"],
    "create-inbound": ["admin", "purchaser", "warehouse"],
    "complete-inbound": ["admin", "purchaser", "warehouse"],
    "create-replenishment": ["admin", "store"],
    "approve-request": ["admin", "manager"],
    "reject-request": ["admin", "manager"],
    "convert-request": ["admin", "manager"],
    "ship-outbound": ["admin", "warehouse"],
    "sign-outbound": ["admin", "store"],
    "generate-recommendations": ["admin", "store", "manager"],
  });

  const STATUS_LABELS = {
    pending: "待处理",
    confirmed: "已确认",
    partial_received: "部分到货",
    completed: "已完成",
    approved: "已通过",
    converted: "已转出库",
    invalidated: "已失效",
    rejected: "已拒绝",
    shipped: "已发货",
    signed: "已签收",
    cancelled: "已取消",
    accepted: "已采用",
    critical_stockout: "严重缺货",
    stockout: "库存不足",
    overstock: "库存积压",
    high: "高风险",
    medium: "中风险",
    low: "低风险",
    warehouse: "仓库",
    store: "门店",
    purchase_inbound: "采购入库",
    outbound: "出库",
    store_outbound: "门店补货出库",
    store_inbound: "门店签收入库",
    adjustment: "库存调整",
    inbound_order: "入库单",
    outbound_order: "出库单",
    example_seed: "示例数据",
  };

  const viewLoaders = {
    dashboard: loadDashboard,
    data: loadBaseData,
    warnings: loadWarnings,
    inbound: loadInbound,
    fulfillment: loadFulfillment,
    transactions: loadTransactions,
    recommendations: loadRecommendations,
    analytics: loadAnalytics,
    suppliers: loadSuppliers,
    system: loadSystemStatus,
  };

  const state = {
    currentRole: null,
    currentUser: null,
    currentView: "dashboard",
    inventoryTab: "overview",
    inventoryOverviewPage: 1,
    transactionPage: 1,
    eventsBound: false,
    lookupsLoaded: false,
    loadedViews: new Set(),
    loadedInventoryTabs: new Set(),
    inventoryOverviewRows: [],
    inventoryWarningRows: [],
    transactionsRows: [],
    products: new Map(),
    suppliers: new Map(),
    supplierProductsBySupplier: new Map(),
    supplierIdsByProduct: new Map(),
    warehouses: new Map(),
    stores: new Map(),
    pendingProductSupplierId: null,
    pendingSupplierBindingProductId: null,
    pendingSupplierBindingSupplierId: null,
    charts: new Map(),
  };

  const $ = (id) => document.getElementById(id);
  const INVENTORY_OVERVIEW_PAGE_SIZE = 20;
  const TRANSACTION_PAGE_SIZE = 20;

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function listItems(data) {
    if (Array.isArray(data)) return data;
    return Array.isArray(data?.items) ? data.items : [];
  }

  function formatNumber(value, maximumFractionDigits = 0) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "--";
    return number.toLocaleString("zh-CN", { maximumFractionDigits });
  }

  function formatTime(value) {
    if (!value) return "--";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return escapeHtml(value);
    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  function label(value) {
    return STATUS_LABELS[value] || value || "--";
  }

  function setText(id, value) {
    const element = $(id);
    if (element) element.textContent = value;
  }

  function showAlert(message, type = "danger") {
    const alert = $("pageAlert");
    if (!alert) return;
    alert.className = `page-alert ${type}`;
    alert.textContent = message;
    alert.hidden = false;
  }

  function clearAlert() {
    const alert = $("pageAlert");
    if (alert) alert.hidden = true;
  }

  function showToast(message, type = "success") {
    const container = $("toastContainer");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `app-toast toast-${type}`;
    toast.setAttribute("role", "status");
    toast.innerHTML = `
      <span class="toast-mark">${type === "success" ? "✓" : "!"}</span>
      <div><strong>${type === "success" ? "操作成功" : "操作失败"}</strong><span>${escapeHtml(message)}</span></div>
      <button type="button" aria-label="关闭提示">×</button>
    `;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("show"));
    const close = () => {
      toast.classList.remove("show");
      window.setTimeout(() => toast.remove(), 220);
    };
    toast.querySelector("button").addEventListener("click", close);
    window.setTimeout(close, 3600);
  }

  function setButtonLoading(button, loading, loadingText = "处理中…") {
    if (!button) return;
    const labelElement = button.querySelector(".btn-label");
    if (loading) {
      button.dataset.originalLabel = labelElement?.textContent || button.textContent;
      button.disabled = true;
      button.classList.add("is-loading");
      if (labelElement) labelElement.textContent = loadingText;
      else button.textContent = loadingText;
      return;
    }

    const original = button.dataset.originalLabel;
    button.disabled = false;
    button.classList.remove("is-loading");
    if (original) {
      if (labelElement) labelElement.textContent = original;
      else button.textContent = original;
    }
    delete button.dataset.originalLabel;
  }

  async function runButtonAction(button, action, options = {}) {
    setButtonLoading(button, true, options.loadingText);
    try {
      const result = await action();
      if (options.successMessage) {
        const message =
          typeof options.successMessage === "function"
            ? options.successMessage(result)
            : options.successMessage;
        showToast(message);
      }
      return result;
    } catch (error) {
      const message = error?.message || "操作失败，请稍后重试";
      showAlert(message);
      showToast(message, "error");
      return null;
    } finally {
      setButtonLoading(button, false);
    }
  }

  function currentModules() {
    return ROLE_MODULES[state.currentRole] || [];
  }

  function moduleLabel(viewName) {
    return MODULE_DEFINITIONS[viewName]?.label || viewName;
  }

  function hasModuleAccess(viewName) {
    return currentModules().includes(viewName);
  }

  function canDo(action) {
    const roles = ACTION_ROLES[action];
    if (!roles) return true;
    return roles.includes(state.currentRole);
  }

  function buildDemoUser(role, username = role, id = null, realName = null) {
    return {
      id,
      username,
      role,
      real_name: realName || ROLE_LABELS[role] || role,
    };
  }

  async function resolveCurrentUser(role, username = role) {
    const rows = listItems(await API.getUsers());
    const normalizedUsername = String(username || "").trim().toLowerCase();
    const expectedUsername = String(ROLE_BACKEND_USERNAMES[role] || "").trim().toLowerCase();
    const roleCandidates = ROLE_BACKEND_CODES[role] || [role];

    const matched =
      rows.find((item) => String(item.username || "").trim().toLowerCase() === normalizedUsername) ||
      rows.find((item) => String(item.username || "").trim().toLowerCase() === expectedUsername) ||
      rows.find((item) => roleCandidates.includes(String(item.role || "").trim().toLowerCase()));

    if (!matched) {
      throw new Error(`未找到可用的${ROLE_LABELS[role] || role}后端用户，请先初始化演示用户数据`);
    }

    return buildDemoUser(
      role,
      matched.username || username,
      Number(matched.id),
      matched.real_name || ROLE_LABELS[role] || role,
    );
  }

  async function ensureActiveUser() {
    if (!state.currentRole) {
      throw new Error("当前未登录，无法执行该操作");
    }
    const fallbackUsername =
      state.currentUser?.username ||
      window.localStorage.getItem("currentLoginName") ||
      ROLE_BACKEND_USERNAMES[state.currentRole] ||
      state.currentRole;
    state.currentUser = await resolveCurrentUser(state.currentRole, fallbackUsername);
    return state.currentUser;
  }

  function defaultViewForRole() {
    const modules = currentModules();
    if (modules.includes("dashboard")) return "dashboard";
    return modules[0] || "dashboard";
  }

  function updateRoleIdentity() {
    setText("currentRoleLabel", ROLE_LABELS[state.currentRole] || state.currentRole || "--");
  }

  function updateHistory(viewName) {
    const url = new URL(window.location.href);
    if (viewName) url.searchParams.set("view", viewName);
    else url.searchParams.delete("view");
    window.history.replaceState({}, "", `${url.pathname}${url.search}`);
  }

  function renderNavigation() {
    const sideNav = $("sideNav");
    if (!sideNav) return;
    sideNav.innerHTML = currentModules()
      .map(
        (viewName, index) => `
          <button class="nav-item${state.currentView === viewName ? " active" : ""}" type="button" data-view="${viewName}">
            <span class="nav-index">${String(index + 1).padStart(2, "0")}</span>
            <span>${escapeHtml(moduleLabel(viewName))}</span>
          </button>`,
      )
      .join("");
  }

  function syncDashboardVisibility() {
    document.querySelectorAll("[data-dashboard-module]").forEach((node) => {
      const required = node.dataset.dashboardModule
        .split(/\s+/)
        .map((item) => item.trim())
        .filter(Boolean);
      node.hidden = required.some((moduleName) => !hasModuleAccess(moduleName));
    });

    const operationsGrid = $("dashboardOperationsGrid");
    if (operationsGrid) {
      const visibleCards = [...operationsGrid.children].filter((child) => !child.hidden).length;
      operationsGrid.classList.toggle("single-column", visibleCards <= 1);
    }
  }

  function applyActionVisibility() {
    document.querySelectorAll("[data-action-permission]").forEach((node) => {
      const allowed = canDo(node.dataset.actionPermission);
      node.hidden = !allowed;
      if (
        node instanceof HTMLButtonElement ||
        node instanceof HTMLInputElement ||
        node instanceof HTMLSelectElement ||
        node instanceof HTMLTextAreaElement
      ) {
        node.disabled = !allowed;
      }
    });
  }

  function closeMobileMenu() {
    $("appSidebar").classList.remove("is-open");
    $("mobileMenuBtn").setAttribute("aria-expanded", "false");
  }

  function activateView(viewName) {
    document.querySelectorAll(".app-view").forEach((view) => {
      view.classList.toggle("active", view.id === `view-${viewName}`);
    });
    document.querySelectorAll(".nav-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.view === viewName);
    });
    setText("pageTitle", moduleLabel(viewName));
  }

  function nameFrom(map, id, fallback) {
    return map.get(Number(id))?.name || `${fallback} ${id ?? "--"}`;
  }

  function productName(id) {
    return nameFrom(state.products, id, "商品");
  }

  function supplierName(id) {
    return nameFrom(state.suppliers, id, "供应商");
  }

  function warehouseName(id) {
    return nameFrom(state.warehouses, id, "仓库");
  }

  function storeName(id) {
    return nameFrom(state.stores, id, "门店");
  }

  function locationName(item) {
    if (!item) return "--";
    if (item.location_name) return item.location_name;
    return item.location_type === "warehouse"
      ? warehouseName(item.warehouse_id)
      : storeName(item.store_id);
  }

  function availableQuantity(item) {
    const directValue = Number(item?.available_quantity);
    if (Number.isFinite(directValue)) return directValue;
    return Number(item?.current_quantity || 0) - Number(item?.frozen_quantity || 0);
  }

  function inventoryLocationKey(item) {
    if (!item) return "";
    if (item.location_type === "warehouse" && item.warehouse_id) {
      return `warehouse:${item.warehouse_id}`;
    }
    if (item.location_type === "store" && item.store_id) {
      return `store:${item.store_id}`;
    }
    return "";
  }

  function inventoryLocationLabel(item) {
    if (!item) return "--";
    return locationName(item);
  }

  function sortInventoryRows(rows) {
    return [...rows].sort((left, right) => {
      const typeCompare = String(left.location_type || "").localeCompare(String(right.location_type || ""), "zh-CN");
      if (typeCompare !== 0) return typeCompare;
      const locationCompare = locationName(left).localeCompare(locationName(right), "zh-CN");
      if (locationCompare !== 0) return locationCompare;
      const productCompare = String(left.product_name || productName(left.product_id)).localeCompare(
        String(right.product_name || productName(right.product_id)),
        "zh-CN",
      );
      if (productCompare !== 0) return productCompare;
      return Number(left.id || 0) - Number(right.id || 0);
    });
  }

  function refreshInventoryLocationFilter() {
    const select = $("inventoryLocationFilter");
    if (!select) return "all";

    const locationType = $("inventoryLocationTypeFilter")?.value || "all";
    const previousValue = select.value || "all";
    const placeholder =
      locationType === "warehouse"
        ? "全部仓库"
        : locationType === "store"
          ? "全部门店"
          : "全部仓库与门店";

    const locationMap = new Map();
    state.inventoryOverviewRows.forEach((item) => {
      if (locationType !== "all" && item.location_type !== locationType) return;
      const key = inventoryLocationKey(item);
      if (!key || locationMap.has(key)) return;
      locationMap.set(key, {
        key,
        label: inventoryLocationLabel(item),
      });
    });

    const options = [`<option value="all">${escapeHtml(placeholder)}</option>`];
    sortInventoryRows(
      [...locationMap.values()].map((entry) => {
        const [type, id] = entry.key.split(":");
        return {
          location_type: type,
          warehouse_id: type === "warehouse" ? Number(id) : null,
          store_id: type === "store" ? Number(id) : null,
          location_name: entry.label,
        };
      }),
    ).forEach((item) => {
      const key = inventoryLocationKey(item);
      options.push(`<option value="${escapeHtml(key)}">${escapeHtml(inventoryLocationLabel(item))}</option>`);
    });

    select.innerHTML = options.join("");
    select.value = locationMap.has(previousValue) ? previousValue : "all";
    return select.value;
  }

  function renderInventoryLocationSummary(rows) {
    const target = $("inventoryLocationSummary");
    if (!target) return;
    const selectedKey = $("inventoryLocationFilter")?.value || "all";
    if (selectedKey === "all") {
      target.hidden = true;
      target.innerHTML = "";
      return;
    }

    const matchedRows = rows.filter((item) => inventoryLocationKey(item) === selectedKey);
    if (!matchedRows.length) {
      target.hidden = true;
      target.innerHTML = "";
      return;
    }

    const summary = {
      label: locationName(matchedRows[0]),
      locationType: label(matchedRows[0].location_type),
      skuCount: 0,
      currentQuantity: 0,
      availableQuantity: 0,
    };

    matchedRows.forEach((item) => {
      summary.skuCount += 1;
      summary.currentQuantity += Number(item.current_quantity || 0);
      summary.availableQuantity += availableQuantity(item);
    });

    target.hidden = false;
    target.innerHTML = `
      <article class="inventory-location-card">
        <div class="inventory-location-top">
          <strong>${escapeHtml(summary.label)}</strong>
          <span class="soft-badge">${escapeHtml(summary.locationType)}</span>
        </div>
        <div class="inventory-location-metrics">
          <div><span>商品数</span><strong>${formatNumber(summary.skuCount)}</strong></div>
          <div><span>当前库存</span><strong>${formatNumber(summary.currentQuantity)}</strong></div>
          <div><span>可用库存</span><strong>${formatNumber(summary.availableQuantity)}</strong></div>
        </div>
      </article>`;
  }

  function renderInventoryPagination(total) {
    const container = $("inventoryOverviewPagination");
    const prevButton = $("inventoryPrevPageBtn");
    const nextButton = $("inventoryNextPageBtn");
    if (!container || !prevButton || !nextButton) return;

    const totalPages = Math.max(1, Math.ceil(total / INVENTORY_OVERVIEW_PAGE_SIZE));
    const currentPage = Math.min(state.inventoryOverviewPage, totalPages);
    state.inventoryOverviewPage = currentPage;

    if (total <= INVENTORY_OVERVIEW_PAGE_SIZE) {
      container.hidden = true;
      setText("inventoryPageInfo", `第 1 / 1 页`);
      prevButton.disabled = true;
      nextButton.disabled = true;
      return;
    }

    container.hidden = false;
    setText("inventoryPageInfo", `第 ${currentPage} / ${totalPages} 页 · 共 ${total} 条`);
    prevButton.disabled = currentPage <= 1;
    nextButton.disabled = currentPage >= totalPages;
  }

  function setInventoryOverviewPage(page) {
    const safePage = Math.max(1, Number(page || 1));
    if (state.inventoryOverviewPage === safePage) return;
    state.inventoryOverviewPage = safePage;
    renderInventoryOverview();
  }

  function getInventoryOverviewBaseRows() {
    const keyword = String($("inventoryKeywordInput")?.value || "")
      .trim()
      .toLowerCase();
    const locationType = $("inventoryLocationTypeFilter")?.value || "all";
    const selectedLocationKey = $("inventoryLocationFilter")?.value || "all";
    return sortInventoryRows(
      state.inventoryOverviewRows.filter((item) => {
        const matchesKeyword =
          !keyword ||
          String(item.product_name || productName(item.product_id))
            .toLowerCase()
            .includes(keyword);
        const matchesType = locationType === "all" || item.location_type === locationType;
        const matchesLocation =
          selectedLocationKey === "all" || inventoryLocationKey(item) === selectedLocationKey;
        return matchesKeyword && matchesType && matchesLocation;
      }),
    );
  }

  function statusBadge(status) {
    return `<span class="status-badge status-${escapeHtml(status || "unknown")}">${escapeHtml(label(status))}</span>`;
  }

  function emptyRow(colspan, message) {
    return `<tr><td colspan="${colspan}"><div class="table-empty">${escapeHtml(message)}</div></td></tr>`;
  }

  function permissionNote() {
    return '<span class="permission-note">当前角色无权限操作</span>';
  }

  function setInventoryTab(tabName) {
    state.inventoryTab = tabName;
    document.querySelectorAll("[data-inventory-tab]").forEach((button) => {
      button.classList.toggle("active", button.dataset.inventoryTab === tabName);
    });
    document.querySelectorAll("[data-inventory-panel]").forEach((panel) => {
      const active = panel.dataset.inventoryPanel === tabName;
      panel.hidden = !active;
      panel.classList.toggle("active", active);
    });
  }

  async function loadLookups(force = false) {
    if (state.lookupsLoaded && !force) {
      populateBusinessSelects();
      return;
    }

    const tasks = [
      [API.getProducts, state.products],
      [API.getSuppliers, state.suppliers],
      [API.getWarehouses, state.warehouses],
      [API.getStores, state.stores],
    ];
    const results = await Promise.allSettled(tasks.map(([loader]) => loader()));
    results.forEach((result, index) => {
      if (result.status !== "fulfilled") return;
      const map = tasks[index][1];
      map.clear();
      listItems(result.value).forEach((item) => map.set(Number(item.id), item));
    });

    state.supplierProductsBySupplier.clear();
    state.supplierIdsByProduct.clear();
    const supplierRows = [...state.suppliers.values()];
    const supplierProductResults = await Promise.allSettled(
      supplierRows.map((item) => API.getSupplierProducts(item.id)),
    );
    supplierProductResults.forEach((result, index) => {
      const supplierId = Number(supplierRows[index]?.id || 0);
      const relations = result.status === "fulfilled" ? listItems(result.value) : [];
      state.supplierProductsBySupplier.set(supplierId, relations);
      relations.forEach((relation) => {
        const productId = Number(relation.product_id);
        if (!state.supplierIdsByProduct.has(productId)) {
          state.supplierIdsByProduct.set(productId, []);
        }
        const supplierIds = state.supplierIdsByProduct.get(productId);
        if (!supplierIds.includes(supplierId)) {
          supplierIds.push(supplierId);
        }
      });
    });

    state.lookupsLoaded = true;
    populateBusinessSelects();
  }

  function populateSelect(id, items, placeholder) {
    const select = $(id);
    if (!select) return;
    const currentValue = select.value;
    select.innerHTML = items.length
      ? items
          .map(
            (item) =>
              `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`,
          )
          .join("")
      : `<option value="">${escapeHtml(placeholder)}</option>`;
    if (items.some((item) => String(item.id) === currentValue)) {
      select.value = currentValue;
    }
  }

  function normalizeSearchText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function productSearchLabel(item) {
    return item?.product_code ? `${item.name} · ${item.product_code}` : item?.name || "--";
  }

  function supplierSearchLabel(item) {
    return item?.name || "--";
  }

  function findSearchItem(items, keyword, formatter, aliases = []) {
    const normalized = normalizeSearchText(keyword);
    if (!normalized) return null;
    return (
      items.find((item) => {
        const candidates = [formatter(item), ...aliases.map((resolver) => resolver(item))];
        return candidates.some((candidate) => normalizeSearchText(candidate) === normalized);
      }) || null
    );
  }

  function populateSearchPicker({
    inputId,
    hiddenId,
    datalistId,
    items,
    formatter,
    aliases = [],
    placeholder,
    disabled = false,
    keepTypedValue = false,
  }) {
    const input = $(inputId);
    const hidden = $(hiddenId);
    const datalist = $(datalistId);
    if (!input || !hidden || !datalist) return;

    const currentHiddenValue = String(hidden.value || "");
    const selectedItem = items.find((item) => String(item.id) === currentHiddenValue) || null;

    datalist.innerHTML = items
      .map((item) => `<option value="${escapeHtml(formatter(item))}"></option>`)
      .join("");
    input.disabled = disabled;
    input.placeholder = placeholder;

    if (selectedItem) {
      input.value = formatter(selectedItem);
      hidden.value = String(selectedItem.id);
      return;
    }

    const matched = keepTypedValue ? findSearchItem(items, input.value, formatter, aliases) : null;
    if (matched) {
      input.value = formatter(matched);
      hidden.value = String(matched.id);
      return;
    }

    hidden.value = "";
    if (!keepTypedValue || disabled) {
      input.value = "";
    }
  }

  function syncSearchPickerSelection(inputId, hiddenId, items, formatter, aliases = []) {
    const input = $(inputId);
    const hidden = $(hiddenId);
    if (!input || !hidden) return null;
    const matched = findSearchItem(items, input.value, formatter, aliases);
    hidden.value = matched ? String(matched.id) : "";
    return matched;
  }

  function applySearchPickerSelection(inputId, hiddenId, items, formatter, selectedId) {
    const input = $(inputId);
    const hidden = $(hiddenId);
    if (!input || !hidden || !selectedId || hidden.value) return;
    const selectedItem = items.find((item) => Number(item.id) === Number(selectedId));
    if (!selectedItem) return;
    hidden.value = String(selectedItem.id);
    input.value = formatter(selectedItem);
  }

  function syncInboundProductPicker() {
    const matched = syncSearchPickerSelection(
      "inboundProductSearch",
      "inboundProduct",
      inboundProducts(),
      productSearchLabel,
      [(item) => item.name, (item) => item.product_code, (item) => String(item.id)],
    );
    if (matched) {
      $("inboundProductSearch").value = productSearchLabel(matched);
    }
    refreshInboundSupplierPicker();
  }

  function syncInboundSupplierPicker() {
    const productId = Number($("inboundProduct")?.value || 0);
    const matched = syncSearchPickerSelection(
      "inboundSupplierSearch",
      "inboundSupplier",
      inboundSuppliersForProduct(productId),
      supplierSearchLabel,
      [(item) => item.name, (item) => String(item.id)],
    );
    if (matched) {
      $("inboundSupplierSearch").value = supplierSearchLabel(matched);
    }
  }

  function syncRequestProductPicker() {
    const matched = syncSearchPickerSelection(
      "requestProductSearch",
      "requestProduct",
      [...state.products.values()],
      productSearchLabel,
      [(item) => item.name, (item) => item.product_code, (item) => String(item.id)],
    );
    if (matched) {
      $("requestProductSearch").value = productSearchLabel(matched);
    }
  }

  function inboundProducts() {
    return [...state.products.values()];
  }

  function inboundSuppliersForProduct(productId) {
    if (!state.supplierIdsByProduct.size) {
      return [...state.suppliers.values()];
    }
    const supplierIds = state.supplierIdsByProduct.get(Number(productId)) || [];
    return supplierIds
      .map((supplierId) => state.suppliers.get(Number(supplierId)))
      .filter(Boolean);
  }

  function refreshInboundSupplierPicker() {
    const productId = Number($("inboundProduct")?.value || 0);
    const suppliers = productId ? inboundSuppliersForProduct(productId) : [];
    populateSearchPicker({
      inputId: "inboundSupplierSearch",
      hiddenId: "inboundSupplier",
      datalistId: "inboundSupplierOptions",
      items: suppliers,
      formatter: supplierSearchLabel,
      aliases: [(item) => item.name, (item) => String(item.id)],
      placeholder: productId
        ? suppliers.length
          ? "搜索供应商名称"
          : "当前商品暂无匹配供应商"
        : "请先选择商品",
      disabled: !productId || !suppliers.length,
      keepTypedValue: false,
    });
  }

  function populateSupplierBindingPickers() {
    const products = [...state.products.values()];
    const suppliers = [...state.suppliers.values()];

    populateSearchPicker({
      inputId: "bindProductSearch",
      hiddenId: "bindProduct",
      datalistId: "bindProductOptions",
      items: products,
      formatter: productSearchLabel,
      aliases: [(item) => item.name, (item) => item.product_code, (item) => String(item.id)],
      placeholder: "搜索商品名称或编码",
      keepTypedValue: true,
    });
    populateSearchPicker({
      inputId: "bindSupplierSearch",
      hiddenId: "bindSupplier",
      datalistId: "bindSupplierOptions",
      items: suppliers,
      formatter: supplierSearchLabel,
      aliases: [(item) => item.name, (item) => String(item.id)],
      placeholder: "搜索供应商名称",
      keepTypedValue: true,
    });

    applySearchPickerSelection(
      "bindProductSearch",
      "bindProduct",
      products,
      productSearchLabel,
      state.pendingSupplierBindingProductId,
    );
    applySearchPickerSelection(
      "bindSupplierSearch",
      "bindSupplier",
      suppliers,
      supplierSearchLabel,
      state.pendingSupplierBindingSupplierId,
    );

    if ($("bindProduct")?.value) {
      state.pendingSupplierBindingProductId = null;
    }
    if ($("bindSupplier")?.value) {
      state.pendingSupplierBindingSupplierId = null;
    }
  }

  function populateProductSupplierPicker() {
    const suppliers = [...state.suppliers.values()];
    populateSearchPicker({
      inputId: "productSupplierSearch",
      hiddenId: "productSupplier",
      datalistId: "productSupplierOptions",
      items: suppliers,
      formatter: supplierSearchLabel,
      aliases: [(item) => item.name, (item) => String(item.id)],
      placeholder: "搜索供应商名称",
      keepTypedValue: true,
    });

    applySearchPickerSelection(
      "productSupplierSearch",
      "productSupplier",
      suppliers,
      supplierSearchLabel,
      state.pendingProductSupplierId,
    );

    if ($("productSupplier")?.value) {
      state.pendingProductSupplierId = null;
    }
  }

  function populateBusinessSelects() {
    const products = [...state.products.values()];
    populateProductSupplierPicker();
    populateSearchPicker({
      inputId: "inboundProductSearch",
      hiddenId: "inboundProduct",
      datalistId: "inboundProductOptions",
      items: inboundProducts(),
      formatter: productSearchLabel,
      aliases: [(item) => item.name, (item) => item.product_code, (item) => String(item.id)],
      placeholder: "搜索商品名称或编码",
      keepTypedValue: true,
    });
    refreshInboundSupplierPicker();
    populateSelect("inboundWarehouse", [...state.warehouses.values()], "暂无仓库");
    populateSelect("requestStore", [...state.stores.values()], "暂无门店");
    populateSearchPicker({
      inputId: "requestProductSearch",
      hiddenId: "requestProduct",
      datalistId: "requestProductOptions",
      items: products,
      formatter: productSearchLabel,
      aliases: [(item) => item.name, (item) => item.product_code, (item) => String(item.id)],
      placeholder: "搜索商品名称或编码",
      keepTypedValue: true,
    });
    populateSupplierBindingPickers();
  }

  async function loadBaseData() {
    await loadLookups(true);
    setText("dataProductCount", formatNumber(state.products.size));
    setText("dataSupplierCount", formatNumber(state.suppliers.size));
    setText("dataWarehouseCount", formatNumber(state.warehouses.size));
    setText("dataStoreCount", formatNumber(state.stores.size));
    state.loadedViews.add("data");
  }

  function updateChart(id, option) {
    const target = $(id);
    if (!target) return;
    if (!window.echarts) {
      target.innerHTML = '<div class="empty-block">图表组件未加载，请检查网络后刷新</div>';
      return;
    }
    let chart = state.charts.get(id);
    if (!chart) {
      target.innerHTML = "";
      chart = window.echarts.init(target);
      state.charts.set(id, chart);
    }
    chart.setOption(option, true);
  }

  function baseChartOption() {
    return {
      animationDuration: 500,
      textStyle: { fontFamily: '"Microsoft YaHei", "PingFang SC", sans-serif' },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(22, 32, 51, .94)",
        borderWidth: 0,
        textStyle: { color: "#fff" },
      },
      grid: { left: 18, right: 26, top: 20, bottom: 12, containLabel: true },
    };
  }

  async function loadDashboard() {
    syncDashboardVisibility();
    await loadLookups();

    const showWarnings = hasModuleAccess("warnings");
    const showRecommendations = hasModuleAccess("recommendations");

    const [dashboard, ranking, warnings, recommendations] = await Promise.all([
      API.getDashboard(),
      showWarnings ? API.getInventoryRanking() : Promise.resolve([]),
      showWarnings ? API.getWarnings() : Promise.resolve([]),
      showRecommendations ? API.getRecommendations() : Promise.resolve([]),
    ]);

    setText("metricProducts", formatNumber(dashboard.product_count));
    setText("metricSuppliers", formatNumber(dashboard.supplier_count));
    setText("metricWarehouses", formatNumber(dashboard.warehouse_count));
    setText("metricStores", formatNumber(dashboard.store_count));
    setText("metricInventory", formatNumber(dashboard.total_inventory_quantity));
    setText("metricStockout", formatNumber(dashboard.stockout_count));
    setText("metricOverstock", formatNumber(dashboard.overstock_count));
    setText(
      "metricWarnings",
      formatNumber(Number(dashboard.stockout_count || 0) + Number(dashboard.overstock_count || 0)),
    );
    setText("metricOutbound", formatNumber(dashboard.recent_outbound_quantity));
    setText("metricRecommendations", formatNumber(dashboard.ai_recommendation_count));
    setText("metricHighRisk", formatNumber(dashboard.high_risk_recommendation_count));
    setText("dashboardUpdatedAt", new Date().toLocaleTimeString("zh-CN", { hour12: false }));

    if (showWarnings) {
      const rankingRows = listItems(ranking).slice(0, 10);
      updateChart("dashboardInventoryChart", {
        ...baseChartOption(),
        xAxis: {
          type: "value",
          axisLabel: { color: "#7a879c" },
          splitLine: { lineStyle: { color: "#edf1f7" } },
        },
        yAxis: {
          type: "category",
          inverse: true,
          data: rankingRows.map((item) => item.product_name),
          axisLabel: { color: "#4d5b70", width: 90, overflow: "truncate" },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        series: [
          {
            name: "库存数量",
            type: "bar",
            data: rankingRows.map((item) => Number(item.quantity || 0)),
            barWidth: 13,
            itemStyle: {
              borderRadius: [0, 7, 7, 0],
              color: new window.echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: "#5667e8" },
                { offset: 1, color: "#8b7cf6" },
              ]),
            },
          },
        ],
      });
      renderDashboardRisks(listItems(warnings));
    }

    if (showRecommendations) {
      renderDashboardRecommendations(listItems(recommendations));
    }

    state.loadedViews.add("dashboard");
  }

  function renderDashboardRisks(rows) {
    const target = $("dashboardRiskList");
    if (!target) return;
    if (!rows.length) {
      target.innerHTML = '<div class="empty-block success-empty">当前没有库存预警</div>';
      return;
    }
    target.innerHTML = rows
      .slice(0, 5)
      .map(
        (item) => `
          <div class="compact-risk">
            <span class="risk-bar ${escapeHtml(item.warning_type)}"></span>
            <div>
              <strong>${escapeHtml(item.product_name || productName(item.product_id))}</strong>
              <small>${escapeHtml(item.location_name || label(item.location_type))} · ${escapeHtml(label(item.warning_type))}</small>
            </div>
            <div class="risk-value">
              <strong>${formatNumber(item.available_quantity ?? item.current_quantity)}</strong>
              <small>安全库存 ${formatNumber(item.safety_stock)}</small>
            </div>
          </div>`,
      )
      .join("");
  }

  function renderDashboardRecommendations(rows) {
    const target = $("dashboardRecommendationList");
    if (!target) return;
    if (!rows.length) {
      target.innerHTML = '<div class="empty-block">暂无补货建议</div>';
      return;
    }
    const riskOrder = { high: 0, medium: 1, low: 2 };
    target.innerHTML = [...rows]
      .sort((a, b) => (riskOrder[a.risk_level] ?? 3) - (riskOrder[b.risk_level] ?? 3))
      .slice(0, 4)
      .map(
        (item) => `
          <div class="dashboard-recommendation">
            <div>
              ${statusBadge(item.risk_level)}
              <strong>${escapeHtml(productName(item.product_id))}</strong>
              <small>${escapeHtml(storeName(item.store_id))} · 规则型智能补货建议</small>
            </div>
            <div class="dashboard-recommendation-quantity">
              <span>建议补货量</span>
              <strong>${formatNumber(item.recommended_quantity)}</strong>
            </div>
          </div>`,
      )
      .join("");
  }

  function renderInventoryOverview() {
    refreshInventoryLocationFilter();
    const rows = getInventoryOverviewBaseRows();
    renderInventoryLocationSummary(rows);

    const total = rows.length;
    const totalPages = Math.max(1, Math.ceil(total / INVENTORY_OVERVIEW_PAGE_SIZE));
    if (state.inventoryOverviewPage > totalPages) {
      state.inventoryOverviewPage = totalPages;
    }
    const startIndex = (state.inventoryOverviewPage - 1) * INVENTORY_OVERVIEW_PAGE_SIZE;
    const pagedRows = rows.slice(startIndex, startIndex + INVENTORY_OVERVIEW_PAGE_SIZE);

    setText("inventoryOverviewResultBadge", `共 ${total} 条记录`);
    $("inventoryOverviewTableBody").innerHTML = pagedRows.length
      ? pagedRows
          .map(
            (item) => `
              <tr>
                <td><strong>${escapeHtml(item.product_name || productName(item.product_id))}</strong><small class="cell-subtitle">ID ${escapeHtml(item.product_id)}</small></td>
                <td>${escapeHtml(label(item.location_type))}</td>
                <td>${escapeHtml(locationName(item))}</td>
                <td class="number-cell">${formatNumber(item.current_quantity)}</td>
                <td class="number-cell">${formatNumber(item.frozen_quantity)}</td>
                <td class="number-cell">${formatNumber(availableQuantity(item))}</td>
                <td class="number-cell">${formatNumber(item.safety_stock)}</td>
                <td class="number-cell">${formatNumber(item.max_stock)}</td>
                <td>${formatTime(item.last_updated_at)}</td>
              </tr>`,
          )
          .join("")
      : emptyRow(9, "没有符合筛选条件的库存记录");
    renderInventoryPagination(total);
  }

  async function loadInventoryOverview(force = false) {
    await loadLookups();
    if (force || !state.loadedInventoryTabs.has("overview")) {
      state.inventoryOverviewRows = listItems(await API.getInventory());
      state.loadedInventoryTabs.add("overview");
    }
    renderInventoryOverview();
  }

  function renderWarningList(rows) {
    const critical = rows.filter((item) => item.warning_type === "critical_stockout").length;
    const stockout = rows.filter((item) => item.warning_type === "stockout").length;
    const overstock = rows.filter((item) => item.warning_type === "overstock").length;
    setText("warningCriticalCount", formatNumber(critical));
    setText("warningStockoutCount", formatNumber(stockout));
    setText("warningOverstockCount", formatNumber(overstock));
    setText("warningTotalCount", formatNumber(rows.length));
    setText("warningResultBadge", `${rows.length} 条记录`);

    $("warningTableBody").innerHTML = rows.length
      ? rows
          .map(
            (item) => `
              <tr>
                <td>${statusBadge(item.warning_type)}</td>
                <td><strong>${escapeHtml(item.product_name || productName(item.product_id))}</strong><small class="cell-subtitle">ID ${escapeHtml(item.product_id)}</small></td>
                <td>${escapeHtml(locationName(item))}<small class="cell-subtitle">${escapeHtml(label(item.location_type))}</small></td>
                <td class="number-cell">${formatNumber(item.current_quantity)}</td>
                <td class="number-cell">${formatNumber(availableQuantity(item))}</td>
                <td>${formatNumber(item.safety_stock)} / ${formatNumber(item.max_stock)}</td>
                <td class="message-cell">${escapeHtml(item.warning_message || "库存达到预警阈值")}</td>
              </tr>`,
          )
          .join("")
      : emptyRow(7, "当前没有库存预警");
  }

  async function loadInventoryAlerts(force = false) {
    await loadLookups();
    if (force || !state.loadedInventoryTabs.has("alerts")) {
      state.inventoryWarningRows = listItems(await API.getWarnings());
      state.loadedInventoryTabs.add("alerts");
    }
    renderWarningList(state.inventoryWarningRows);
  }

  async function switchInventoryTab(tabName, force = false) {
    setInventoryTab(tabName);
    if (tabName === "alerts") {
      await loadInventoryAlerts(force);
      return;
    }
    await loadInventoryOverview(force);
  }

  async function loadWarnings() {
    await switchInventoryTab(state.inventoryTab || "overview", true);
    state.loadedViews.add("warnings");
  }

  function itemSummary(items) {
    if (!Array.isArray(items) || !items.length) return "暂无明细";
    const total = items.reduce((sum, item) => sum + Number(item.quantity || 0), 0);
    const names = items
      .slice(0, 2)
      .map((item) => productName(item.product_id))
      .join("、");
    return `${names}${items.length > 2 ? ` 等 ${items.length} 项` : ""} · ${formatNumber(total)} 件`;
  }

  async function loadInbound() {
    await loadLookups();
    const rows = listItems(await API.getInboundOrders());
    setText("inboundResultBadge", `${rows.length} 张单据`);
    $("inboundTableBody").innerHTML = rows.length
      ? rows
          .map(
            (item) => `
              <tr>
                <td><strong>${escapeHtml(item.inbound_no)}</strong><small class="cell-subtitle">ID ${escapeHtml(item.id)}</small></td>
                <td>${item.purchase_order_id ? `PO #${escapeHtml(item.purchase_order_id)}` : "--"}</td>
                <td>${escapeHtml(supplierName(item.supplier_id))}</td>
                <td>${escapeHtml(warehouseName(item.warehouse_id))}</td>
                <td>${escapeHtml(itemSummary(item.items))}</td>
                <td>${statusBadge(item.status)}</td>
                <td>${formatTime(item.inbound_time)}</td>
                <td>
                  ${
                    item.status === "pending"
                      ? canDo("complete-inbound")
                        ? `<button class="btn btn-sm btn-primary row-action" type="button" data-action="complete-inbound" data-id="${item.id}"><span class="btn-label">完成入库</span></button>`
                        : permissionNote()
                      : '<span class="done-text">已处理</span>'
                  }
                </td>
              </tr>`,
          )
          .join("")
      : emptyRow(8, "暂无入库单，请先导入演示数据");
    state.loadedViews.add("inbound");
  }

  async function loadFulfillment() {
    await loadLookups();
    const [requests, outbounds] = await Promise.all([
      API.getReplenishmentRequests(),
      API.getOutboundOrders(),
    ]);
    const outboundRows = listItems(outbounds);
    const outboundMap = new Map(outboundRows.map((item) => [Number(item.id), item]));
    renderRequests(listItems(requests), outboundMap);
    renderOutbounds(outboundRows);
    state.loadedViews.add("fulfillment");
  }

  function renderRequests(rows, outboundMap = new Map()) {
    setText("requestResultBadge", `${rows.length} 张申请`);
    $("requestTableBody").innerHTML = rows.length
      ? rows
          .map((item) => {
            const relatedOutbound = outboundMap.get(Number(item.generated_outbound_order_id));
            let action = '<span class="done-text">无需操作</span>';
            if (item.audit_status === "pending") {
              action =
                canDo("approve-request") || canDo("reject-request")
                  ? `<div class="row-action-group">
                      ${
                        canDo("approve-request")
                          ? `<button class="btn btn-sm btn-primary row-action" type="button" data-action="approve-request" data-id="${item.id}"><span class="btn-label">审核通过</span></button>`
                          : ""
                      }
                      ${
                        canDo("reject-request")
                          ? `<button class="btn btn-sm btn-outline-danger row-action" type="button" data-action="reject-request" data-id="${item.id}"><span class="btn-label">拒绝申请</span></button>`
                          : ""
                      }
                    </div>`
                  : permissionNote();
            } else if (item.audit_status === "approved" && !item.generated_outbound_order_id) {
              action = canDo("convert-request")
                ? `<button class="btn btn-sm btn-primary row-action" type="button" data-action="convert-request" data-id="${item.id}"><span class="btn-label">自动分仓生成出库单</span></button>`
                : permissionNote();
            }
            const assignedWarehouse =
              item.source_warehouse_name ||
              relatedOutbound?.source_warehouse_name ||
              (item.source_warehouse_id || relatedOutbound?.source_warehouse_id
                ? warehouseName(item.source_warehouse_id || relatedOutbound?.source_warehouse_id)
                : "待分配");
            const outboundLabel =
              item.outbound_no ||
              relatedOutbound?.outbound_no ||
              (item.generated_outbound_order_id ? `#${item.generated_outbound_order_id}` : "--");
            const assignmentNote =
              item.audit_status === "approved"
                ? "审核后已进入分仓阶段"
                : item.audit_status === "invalidated"
                  ? "自动分仓生成出库单失败，申请已失效"
                  : "系统将按可用库存分配来源仓库";
            const outboundNote = item.generated_outbound_order_id
              ? "已生成出库单"
              : item.audit_status === "invalidated"
                ? "未生成出库单"
                : "待生成出库单";
            return `
              <tr>
                <td><strong>${escapeHtml(item.request_no)}</strong><small class="cell-subtitle">ID ${escapeHtml(item.id)}</small></td>
                <td>${escapeHtml(storeName(item.store_id))}</td>
                <td>${escapeHtml(productName(item.product_id))}</td>
                <td class="number-cell">${formatNumber(item.request_quantity)}</td>
                <td class="message-cell">${escapeHtml(item.request_reason || "--")}</td>
                <td>${statusBadge(item.audit_status)}</td>
                <td>${escapeHtml(assignedWarehouse)}<small class="cell-subtitle">${assignmentNote}</small></td>
                <td>${escapeHtml(outboundLabel)}<small class="cell-subtitle">${outboundNote}</small></td>
                <td>${action}</td>
              </tr>`;
          })
          .join("")
      : emptyRow(9, "暂无补货申请，请先导入演示数据");
  }

  function renderOutbounds(rows) {
    setText("outboundResultBadge", `${rows.length} 张单据`);
    $("outboundTableBody").innerHTML = rows.length
      ? rows
          .map((item) => {
            let action = '<span class="done-text">履约完成</span>';
            if (item.status === "pending") {
              action = canDo("ship-outbound")
                ? `<button class="btn btn-sm btn-primary row-action" type="button" data-action="ship-outbound" data-id="${item.id}"><span class="btn-label">出库发货</span></button>`
                : permissionNote();
            } else if (item.status === "shipped") {
              action = canDo("sign-outbound")
                ? `<button class="btn btn-sm btn-primary row-action" type="button" data-action="sign-outbound" data-id="${item.id}"><span class="btn-label">门店签收</span></button>`
                : permissionNote();
            } else if (item.status === "cancelled") {
              action = '<span class="done-text">已取消</span>';
            }
            return `
              <tr>
                <td><strong>${escapeHtml(item.outbound_no)}</strong><small class="cell-subtitle">ID ${escapeHtml(item.id)}</small></td>
                <td>${escapeHtml(item.source_warehouse_name || warehouseName(item.source_warehouse_id))}<small class="cell-subtitle">系统分配来源仓库</small></td>
                <td>${escapeHtml(item.target_store_name || storeName(item.target_store_id))}<small class="cell-subtitle">目标门店</small></td>
                <td>${escapeHtml(itemSummary(item.items))}</td>
                <td>${item.source_request_id ? `RR #${escapeHtml(item.source_request_id)}` : "--"}</td>
                <td>${statusBadge(item.status)}</td>
                <td>${formatTime(item.outbound_time)}</td>
                <td>${action}</td>
              </tr>`;
          })
          .join("")
      : emptyRow(8, "暂无出库单，审核补货申请后可生成");
  }

  function transactionLocationLabel(locationType, warehouseId, storeId) {
    if (locationType === "warehouse" && warehouseId) return warehouseName(warehouseId);
    if (locationType === "store" && storeId) return storeName(storeId);
    return null;
  }

  function transactionPathText(item) {
    const source = transactionLocationLabel(
      item.source_location_type,
      item.source_warehouse_id,
      item.source_store_id,
    );
    const target = transactionLocationLabel(
      item.target_location_type,
      item.target_warehouse_id,
      item.target_store_id,
    );
    if (item.transaction_type === "store_outbound" && source && target) {
      return `${source} → 在途（发往 ${target}）`;
    }
    if (item.transaction_type === "store_inbound" && source && target) {
      return `在途（来自 ${source}） → ${target}`;
    }
    if (source && target) return `${source} → ${target}`;
    if (source) return `${source} → 外部`;
    if (target) return `外部 → ${target}`;
    return "系统内部调整";
  }

  function transactionStageNote(item) {
    if (item.transaction_type === "store_outbound") {
      return "发货时先扣减仓库库存";
    }
    if (item.transaction_type === "store_inbound") {
      return "门店签收后再增加门店库存";
    }
    if (item.transaction_type === "purchase_inbound") {
      return "采购到货后增加仓库库存";
    }
    return item.remark || "";
  }

  function populateTransactionFilters(rows) {
    const warehouseSelect = $("transactionWarehouseFilter");
    const typeSelect = $("transactionTypeFilter");
    if (!warehouseSelect || !typeSelect) return;

    const currentWarehouse = warehouseSelect.value || "all";
    const currentType = typeSelect.value || "all";
    const warehouseIds = new Set();
    const typeSet = new Set();

    rows.forEach((item) => {
      if (item.source_warehouse_id) warehouseIds.add(Number(item.source_warehouse_id));
      if (item.target_warehouse_id) warehouseIds.add(Number(item.target_warehouse_id));
      if (item.transaction_type) typeSet.add(String(item.transaction_type));
    });

    const warehouseOptions = [`<option value="all">全部仓库</option>`];
    [...warehouseIds]
      .sort((a, b) => warehouseName(a).localeCompare(warehouseName(b), "zh-CN"))
      .forEach((warehouseId) => {
        warehouseOptions.push(
          `<option value="${warehouseId}">${escapeHtml(warehouseName(warehouseId))}</option>`,
        );
      });
    warehouseSelect.innerHTML = warehouseOptions.join("");
    warehouseSelect.value = [...warehouseIds].includes(Number(currentWarehouse))
      ? currentWarehouse
      : "all";

    const typeOptions = [`<option value="all">全部类型</option>`];
    [...typeSet]
      .sort((a, b) => label(a).localeCompare(label(b), "zh-CN"))
      .forEach((type) => {
        typeOptions.push(`<option value="${escapeHtml(type)}">${escapeHtml(label(type))}</option>`);
      });
    typeSelect.innerHTML = typeOptions.join("");
    typeSelect.value = typeSet.has(currentType) ? currentType : "all";
  }

  function getFilteredTransactionRows() {
    const keyword = normalizeSearchText($("transactionKeywordInput")?.value || "");
    const warehouseFilter = $("transactionWarehouseFilter")?.value || "all";
    const typeFilter = $("transactionTypeFilter")?.value || "all";
    const sortOrder = $("transactionSortFilter")?.value || "desc";

    return [...state.transactionsRows]
      .filter((item) => {
        const matchesKeyword =
          !keyword ||
          [
            item.transaction_no,
            productName(item.product_id),
            item.related_doc_type ? label(item.related_doc_type) : "",
            item.related_doc_id != null ? String(item.related_doc_id) : "",
            transactionPathText(item),
            transactionStageNote(item),
            item.remark,
          ].some((value) => normalizeSearchText(value).includes(keyword));

        const matchesWarehouse =
          warehouseFilter === "all" ||
          Number(item.source_warehouse_id || 0) === Number(warehouseFilter) ||
          Number(item.target_warehouse_id || 0) === Number(warehouseFilter);

        const matchesType = typeFilter === "all" || String(item.transaction_type) === typeFilter;
        return matchesKeyword && matchesWarehouse && matchesType;
      })
      .sort((left, right) => {
        const diff = new Date(left.transaction_time).getTime() - new Date(right.transaction_time).getTime();
        return sortOrder === "asc" ? diff : -diff;
      });
  }

  function renderTransactionPagination(total) {
    const container = $("transactionPagination");
    const prevButton = $("transactionPrevPageBtn");
    const nextButton = $("transactionNextPageBtn");
    if (!container || !prevButton || !nextButton) return;

    const totalPages = Math.max(1, Math.ceil(total / TRANSACTION_PAGE_SIZE));
    const currentPage = Math.min(state.transactionPage, totalPages);
    state.transactionPage = currentPage;

    if (total <= TRANSACTION_PAGE_SIZE) {
      container.hidden = true;
      setText("transactionPageInfo", "第 1 / 1 页");
      prevButton.disabled = true;
      nextButton.disabled = true;
      return;
    }

    container.hidden = false;
    setText("transactionPageInfo", `第 ${currentPage} / ${totalPages} 页 · 共 ${total} 条`);
    prevButton.disabled = currentPage <= 1;
    nextButton.disabled = currentPage >= totalPages;
  }

  function renderTransactions() {
    const rows = getFilteredTransactionRows();
    const total = rows.length;
    const totalPages = Math.max(1, Math.ceil(total / TRANSACTION_PAGE_SIZE));
    if (state.transactionPage > totalPages) {
      state.transactionPage = totalPages;
    }
    const startIndex = (state.transactionPage - 1) * TRANSACTION_PAGE_SIZE;
    const pagedRows = rows.slice(startIndex, startIndex + TRANSACTION_PAGE_SIZE);
    setText("transactionResultBadge", `共 ${total} 条流水`);

    $("transactionTableBody").innerHTML = pagedRows.length
      ? pagedRows
          .map((item) => {
            const quantity = Number(item.change_quantity || 0);
            const relatedDoc =
              item.related_doc_id != null
                ? `${label(item.related_doc_type)} #${item.related_doc_id}`
                : label(item.related_doc_type || "--");
            return `
              <tr>
                <td><strong>${escapeHtml(item.transaction_no)}</strong></td>
                <td>${escapeHtml(productName(item.product_id))}<small class="cell-subtitle">ID ${escapeHtml(item.product_id)}</small></td>
                <td>${statusBadge(item.transaction_type)}</td>
                <td>${escapeHtml(transactionPathText(item))}${transactionStageNote(item) ? `<small class="cell-subtitle">${escapeHtml(transactionStageNote(item))}</small>` : ""}</td>
                <td class="number-cell ${quantity >= 0 ? "quantity-positive" : "quantity-negative"}">${quantity > 0 ? "+" : ""}${formatNumber(quantity)}</td>
                <td class="number-cell">${formatNumber(item.before_quantity)}</td>
                <td class="number-cell">${formatNumber(item.after_quantity)}</td>
                <td>${escapeHtml(relatedDoc)}</td>
                <td>${formatTime(item.transaction_time)}</td>
              </tr>`;
          })
          .join("")
      : emptyRow(9, "暂无库存流水");

    renderTransactionPagination(total);
  }

  function setTransactionPage(page) {
    const safePage = Math.max(1, Number(page || 1));
    if (safePage === state.transactionPage) return;
    state.transactionPage = safePage;
    renderTransactions();
  }

  async function loadTransactions(force = false) {
    await loadLookups();
    state.transactionsRows = listItems(await API.getTransactions());
    populateTransactionFilters(state.transactionsRows);
    renderTransactions();
    state.loadedViews.add("transactions");
  }

  async function loadRecommendations() {
    await loadLookups();
    const rows = listItems(await API.getRecommendations());
    const highRisk = rows.filter((item) => item.risk_level === "high").length;
    const totalQuantity = rows.reduce(
      (sum, item) => sum + Math.max(0, Number(item.recommended_quantity || 0)),
      0,
    );
    setText("recommendationTotal", formatNumber(rows.length));
    setText("recommendationHigh", formatNumber(highRisk));
    setText("recommendationQuantity", formatNumber(totalQuantity));

    const riskOrder = { high: 0, medium: 1, low: 2 };
    const sorted = [...rows].sort(
      (a, b) => (riskOrder[a.risk_level] ?? 3) - (riskOrder[b.risk_level] ?? 3),
    );
    $("recommendationGrid").innerHTML = sorted.length
      ? sorted
          .map(
            (item) => `
              <article class="recommendation-card risk-${escapeHtml(item.risk_level)}">
                <div class="recommendation-head">
                  <div>
                    ${statusBadge(item.risk_level)}
                    <h3>${escapeHtml(storeName(item.store_id))} · ${escapeHtml(productName(item.product_id))}</h3>
                  </div>
                  <div class="recommendation-number"><span>建议补货</span><strong>${formatNumber(item.recommended_quantity)}</strong></div>
                </div>
                <div class="recommendation-stats">
                  <div><span>当前库存</span><strong>${formatNumber(item.current_stock)}</strong></div>
                  <div><span>安全库存</span><strong>${formatNumber(item.safety_stock)}</strong></div>
                  <div><span>近 7 天销量</span><strong>${formatNumber(item.recent_7_sales, 1)}</strong></div>
                  <div><span>预计缺货</span><strong>${item.days_until_stockout == null ? "--" : `${formatNumber(item.days_until_stockout, 1)} 天`}</strong></div>
                </div>
                <p>${escapeHtml(item.reason_enhanced || item.reason || "暂无推荐理由")}</p>
                <footer>
                  <span>推荐：${escapeHtml(supplierName(item.recommended_supplier_id))}</span>
                  <span>${item.llm_used ? "LLM 增强" : "规则模型"}</span>
                </footer>
              </article>`,
          )
          .join("")
      : '<div class="empty-block large-empty">暂无补货建议，点击“生成补货建议”开始分析</div>';
    state.loadedViews.add("recommendations");
  }

  async function loadSuppliers() {
    await loadLookups();
    const ranking = await API.getSupplierRanking();
    const rankingRows = listItems(ranking)
      .map((item) => ({ ...item, score: Number(item.score || 0) }))
      .sort((a, b) => b.score - a.score);

    setText("supplierResultBadge", `${rankingRows.length} 家供应商`);
    $("supplierTableBody").innerHTML = rankingRows.length
      ? rankingRows
          .map(
            (item, index) => `
              <tr>
                <td><span class="rank-number rank-${index + 1}">${index + 1}</span></td>
                <td><strong>${escapeHtml(supplierName(item.supplier_id))}</strong><small class="cell-subtitle">ID ${escapeHtml(item.supplier_id)}</small></td>
                <td><strong class="score-value">${formatNumber(item.score, 1)}</strong></td>
                <td class="message-cell">${escapeHtml(item.score_source || "--")}</td>
                <td>${scoreEvaluation(item.score)}</td>
              </tr>`,
          )
          .join("")
      : emptyRow(5, "暂无供应商评分，请先计算评分");

    updateChart("supplierScoreChart", {
      ...baseChartOption(),
      xAxis: {
        type: "value",
        max: 100,
        axisLabel: { color: "#7a879c" },
        splitLine: { lineStyle: { color: "#edf1f7" } },
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: rankingRows.slice(0, 8).map((item) => supplierName(item.supplier_id)),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: "#4d5b70", width: 100, overflow: "truncate" },
      },
      series: [
        {
          type: "bar",
          data: rankingRows.slice(0, 8).map((item) => item.score),
          barWidth: 13,
          itemStyle: { color: "#7567e8", borderRadius: [5, 5, 5, 5] },
        },
      ],
    });

    state.loadedViews.add("suppliers");
  }

  async function loadAnalytics() {
    const [dashboard, ranking, trend] = await Promise.all([
      API.getDashboard(),
      API.getInventoryRanking(),
      API.getWarehouseFlowTrend(),
    ]);
    const rankingRows = listItems(ranking).slice(0, 10);
    const trendRows = listItems(trend);

    setText(
      "analyticsWarnings",
      formatNumber(Number(dashboard.stockout_count || 0) + Number(dashboard.overstock_count || 0)),
    );
    setText("analyticsOutbound", formatNumber(dashboard.recent_outbound_quantity));
    setText("analyticsRecommendations", formatNumber(dashboard.ai_recommendation_count));
    setText("analyticsProducts", formatNumber(dashboard.product_count));
    setText("analyticsResultBadge", `Top ${rankingRows.length || 0}`);

    updateChart("analyticsInventoryChart", {
      ...baseChartOption(),
      xAxis: {
        type: "value",
        axisLabel: { color: "#7a879c" },
        splitLine: { lineStyle: { color: "#edf1f7" } },
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: rankingRows.map((item) => item.product_name),
        axisLabel: { color: "#4d5b70", width: 90, overflow: "truncate" },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          name: "库存数量",
          type: "bar",
          data: rankingRows.map((item) => Number(item.quantity || 0)),
          barWidth: 13,
          itemStyle: {
            borderRadius: [0, 7, 7, 0],
            color: new window.echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: "#ef8b53" },
              { offset: 1, color: "#f6bd60" },
            ]),
          },
        },
      ],
    });

    const xLabels = trendRows.map(
      (item) => `${item.year}-${String(item.month).padStart(2, "0")} ${item.warehouse_name}`,
    );
    updateChart("warehouseTrendChart", {
      ...baseChartOption(),
      xAxis: {
        type: "category",
        data: xLabels,
        axisLabel: { color: "#7a879c", rotate: xLabels.length > 5 ? 25 : 0 },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: "#dfe5ef" } },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#7a879c" },
        splitLine: { lineStyle: { color: "#edf1f7" } },
      },
      series: [
        {
          name: "出入库量",
          type: "line",
          smooth: true,
          data: trendRows.map((item) => Number(item.warehouse_sales || 0)),
          lineStyle: { color: "#22a981", width: 3 },
          itemStyle: { color: "#5667e8" },
          areaStyle: { color: "rgba(34, 169, 129, .10)" },
        },
      ],
    });

    state.loadedViews.add("analytics");
  }

  function scoreEvaluation(score) {
    if (score >= 90) return '<span class="status-badge status-completed">优秀</span>';
    if (score >= 75) return '<span class="status-badge status-approved">良好</span>';
    if (score >= 60) return '<span class="status-badge status-pending">合格</span>';
    return '<span class="status-badge status-rejected">待改进</span>';
  }

  function setSystemCard(cardId, statusId, detailId, ok, status, detail) {
    const card = $(cardId);
    if (!card) return;
    card.classList.toggle("is-ok", ok);
    card.classList.toggle("is-error", !ok);
    setText(statusId, status);
    setText(detailId, detail);
  }

  async function loadSystemStatus() {
    const [healthResult, databaseResult, exampleResult] = await Promise.allSettled([
      API.getHealth(),
      API.getDatabaseHealth(),
      API.getExampleStatus(),
    ]);

    if (healthResult.status === "fulfilled") {
      const health = healthResult.value;
      setSystemCard(
        "backendHealthCard",
        "backendHealthStatus",
        "backendHealthDetail",
        true,
        "运行正常",
        `${health.app || "Supply Chain Management"} · ${health.database || "connected"}`,
      );
      setText("systemAppName", health.app || "Supply Chain Management");
      $("globalStatusDot").className = "status-dot is-online";
      setText("globalStatusText", "系统运行正常");
      setText("globalStatusDetail", "后端服务已连接");
    } else {
      setSystemCard(
        "backendHealthCard",
        "backendHealthStatus",
        "backendHealthDetail",
        false,
        "连接失败",
        healthResult.reason?.message || "无法连接后端",
      );
      $("globalStatusDot").className = "status-dot is-offline";
      setText("globalStatusText", "系统连接异常");
      setText("globalStatusDetail", healthResult.reason?.message || "请先启动后端服务");
    }

    if (databaseResult.status === "fulfilled") {
      const database = databaseResult.value;
      setSystemCard(
        "databaseHealthCard",
        "databaseHealthStatus",
        "databaseHealthDetail",
        true,
        "连接正常",
        `${database.dialect || "--"} · ${database.status || "connected"}`,
      );
      setText("systemDialect", database.dialect || "--");
      setText("systemDatabaseUrl", database.database_url_masked || "--");
    } else {
      setSystemCard(
        "databaseHealthCard",
        "databaseHealthStatus",
        "databaseHealthDetail",
        false,
        "接口暂不可用",
        databaseResult.reason?.message || "数据库状态接口尚未实现",
      );
      setText("systemDialect", "等待后端接口");
      setText("systemDatabaseUrl", "--");
    }

    if (exampleResult.status === "fulfilled") {
      const example = exampleResult.value;
      setSystemCard(
        "exampleHealthCard",
        "exampleHealthStatus",
        "exampleHealthDetail",
        true,
        "数据已就绪",
        `${formatNumber(example.products)} 商品 · ${formatNumber(example.stores)} 门店 · ${formatNumber(example.stock_transactions)} 流水`,
      );
    } else {
      setSystemCard(
        "exampleHealthCard",
        "exampleHealthStatus",
        "exampleHealthDetail",
        false,
        "状态未知",
        exampleResult.reason?.message || "无法读取演示数据状态",
      );
    }

    const allOk =
      healthResult.status === "fulfilled" &&
      databaseResult.status === "fulfilled" &&
      exampleResult.status === "fulfilled";
    const badge = $("connectionBadge");
    badge.className = `status-badge ${allOk ? "status-completed" : "status-pending"}`;
    badge.textContent = allOk ? "全部正常" : "部分功能待就绪";
    state.loadedViews.add("system");
  }

  async function switchView(viewName, options = {}) {
    if (!viewLoaders[viewName]) return false;
    if (!hasModuleAccess(viewName)) {
      showAlert(`当前角色无权限访问“${moduleLabel(viewName)}”模块`, "warning");
      return false;
    }

    if (viewName === "warnings") {
      state.inventoryTab = options.inventoryTab || "overview";
      setInventoryTab(state.inventoryTab);
    }

    state.currentView = viewName;
    activateView(viewName);
    renderNavigation();
    syncDashboardVisibility();
    applyActionVisibility();
    clearAlert();
    closeMobileMenu();
    updateHistory(viewName);
    window.scrollTo({ top: 0, behavior: "smooth" });

    if (options.load === false) return true;
    if (!options.force && viewName !== "warnings" && state.loadedViews.has(viewName)) return true;

    try {
      await viewLoaders[viewName]();
      state.loadedViews.add(viewName);
      return true;
    } catch (error) {
      showAlert(error?.message || `加载${moduleLabel(viewName)}失败`);
      return false;
    }
  }

  async function refreshView(viewName, button, successMessage = "数据已刷新") {
    if (!viewLoaders[viewName] || !hasModuleAccess(viewName)) {
      showAlert("当前角色无权限刷新该模块", "warning");
      return;
    }
    await runButtonAction(
      button,
      async () => {
        await viewLoaders[viewName]();
        state.loadedViews.add(viewName);
      },
      {
        loadingText: "加载中…",
        successMessage,
      },
    );
  }

  async function handleRowAction(button) {
    const id = Number(button.dataset.id);
    const action = button.dataset.action;
    if (!canDo(action)) {
      showAlert("当前角色无权限操作", "warning");
      showToast("当前角色无权限操作", "error");
      return;
    }

    const currentUser = await ensureActiveUser();
    const configurations = {
      "complete-inbound": {
        request: () => API.completeInbound(id),
        success: "入库完成，目标仓库库存已增加，并已生成库存流水",
        reload: async () => {
          await Promise.all([
            loadInbound(),
            hasModuleAccess("dashboard") ? loadDashboard() : Promise.resolve(),
            hasModuleAccess("transactions") ? loadTransactions() : Promise.resolve(),
          ]);
        },
      },
      "approve-request": {
        request: () => API.approveReplenishment(id, Number(currentUser?.id || 0)),
        success: "补货申请审核通过，可继续自动分仓生成出库单",
        reload: loadFulfillment,
      },
      "reject-request": {
        request: () => API.rejectReplenishment(id, Number(currentUser?.id || 0)),
        success: "补货申请已拒绝，系统未生成出库单",
        reload: loadFulfillment,
      },
      "convert-request": {
        request: () => API.convertReplenishment(id, Number(currentUser?.id || 0)),
        success: (result) =>
          `已生成出库单 ${result.outbound_no || `#${result.outbound_order_id}`}，系统已分配来源仓库：${result.source_warehouse_name || warehouseName(result.source_warehouse_id)}`,
        reload: loadFulfillment,
      },
      "ship-outbound": {
        request: () => API.shipOutbound(id),
        success: "出库发货成功，仓库库存已扣减并写入库存流水",
        reload: async () => {
          await Promise.all([
            loadFulfillment(),
            hasModuleAccess("dashboard") ? loadDashboard() : Promise.resolve(),
            hasModuleAccess("transactions") ? loadTransactions() : Promise.resolve(),
          ]);
        },
      },
      "sign-outbound": {
        request: () => API.signOutbound(id),
        success: "门店签收成功，门店库存已增加，履约流程完成",
        reload: async () => {
          await Promise.all([
            loadFulfillment(),
            hasModuleAccess("dashboard") ? loadDashboard() : Promise.resolve(),
            hasModuleAccess("transactions") ? loadTransactions() : Promise.resolve(),
          ]);
        },
      },
    };

    const config = configurations[action];
    if (!config) return;

    await runButtonAction(
      button,
      async () => {
        const result = await config.request();
        await config.reload();
        return result;
      },
      {
        loadingText: "处理中…",
        successMessage: config.success,
      },
    );
  }

  function formValues(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  function optionalValue(value) {
    const normalized = String(value || "").trim();
    return normalized || null;
  }

  function requireSearchPickerValue(hiddenId, message) {
    const hidden = $(hiddenId);
    const value = Number(hidden?.value || 0);
    if (!value) {
      showAlert(message, "warning");
      showToast(message, "error");
      return null;
    }
    return value;
  }

  function ensureSearchPickerValue(inputId, hiddenId, items, formatter, aliases = []) {
    const matched = syncSearchPickerSelection(inputId, hiddenId, items, formatter, aliases);
    if (matched) {
      const input = $(inputId);
      if (input) {
        input.value = formatter(matched);
      }
    }
    return matched;
  }

  async function handleBaseDataCreate(form) {
    if (!canDo("create-base-data")) {
      showAlert("当前角色无权限操作", "warning");
      return;
    }

    const type = form.dataset.createForm;
    const currentUser = await ensureActiveUser();
    const values = formValues(form);
    let boundProductId = null;
    let boundSupplierId = null;
    if (type === "product") {
      boundSupplierId = requireSearchPickerValue("productSupplier", "请先选择该商品的供货供应商");
      if (!boundSupplierId) return;
    }
    if (type === "supplier-product") {
      boundProductId = requireSearchPickerValue("bindProduct", "请先选择要绑定的商品");
      boundSupplierId = requireSearchPickerValue("bindSupplier", "请先选择供应商");
      if (!boundProductId || !boundSupplierId) return;
    }
    const configurations = {
      product: {
        request: async () => {
          const product = await API.createProduct({
            product_code: values.product_code.trim(),
            name: values.name.trim(),
            spec: optionalValue(values.spec),
            unit: values.unit.trim(),
            default_safety_stock: Number(values.default_safety_stock),
            is_active: true,
          });

          try {
            await API.bindSupplierProduct(boundSupplierId, {
              product_id: Number(product.id),
              supply_price: Number(values.supply_price),
              lead_time_days: Number(values.lead_time_days),
              on_time_rate: Number(values.on_time_rate),
              quality_score: Number(values.quality_score),
              is_preferred: values.is_preferred === "true",
            });
          } catch (error) {
            state.pendingSupplierBindingProductId = Number(product.id) || null;
            state.pendingSupplierBindingSupplierId = Number(boundSupplierId) || null;
            throw new Error(
              `${error?.message || "供应商绑定失败"}。商品已创建，请在“绑定商品与供应商”区域补充供货关系。`,
            );
          }

          return {
            ...product,
            supplier_id: Number(boundSupplierId),
          };
        },
        success: "商品已新增，并已同步绑定供货供应商",
      },
      supplier: {
        request: () =>
          API.createSupplier({
            name: values.name.trim(),
            phone: values.phone.trim(),
            contact_person: optionalValue(values.contact_person),
            supplier_level: optionalValue(values.supplier_level),
            address: optionalValue(values.address),
            cooperation_status: "active",
            is_active: true,
          }),
        success: "供应商已新增",
      },
      "supplier-product": {
        request: () =>
          API.bindSupplierProduct(boundSupplierId, {
            product_id: boundProductId,
            supply_price: Number(values.supply_price),
            lead_time_days: Number(values.lead_time_days),
            on_time_rate: Number(values.on_time_rate),
            quality_score: Number(values.quality_score),
            is_preferred: values.is_preferred === "true",
          }),
        success: "供应关系已保存，后续入库会按商品匹配供应商",
      },
      warehouse: {
        request: () =>
          API.createWarehouse({
            warehouse_code: values.warehouse_code.trim(),
            name: values.name.trim(),
            region: optionalValue(values.region),
            manager_name: optionalValue(values.manager_name),
            address: optionalValue(values.address),
            status: "active",
            is_synthetic: false,
          }),
        success: "仓库节点已新增",
      },
      store: {
        request: () =>
          API.createStore({
            store_code: values.store_code.trim(),
            name: values.name.trim(),
            region: optionalValue(values.region),
            contact_person: optionalValue(values.contact_person),
            address: optionalValue(values.address),
            business_status: "active",
            is_synthetic: false,
          }),
        success: "门店节点已新增",
      },
    };
    const configuration = configurations[type];
    if (!configuration) return;

    const button = form.querySelector('[type="submit"]');
    const result = await runButtonAction(button, configuration.request, {
      loadingText: "保存中…",
      successMessage: configuration.success,
    });
    if (!result) return;

    if (type === "product" && result.id) {
      state.pendingProductSupplierId = null;
      state.pendingSupplierBindingProductId = Number(result.id);
      state.pendingSupplierBindingSupplierId = Number(result.supplier_id || 0) || null;
    }
    if (type === "supplier" && result.id) {
      state.pendingProductSupplierId = Number(result.id);
      state.pendingSupplierBindingSupplierId = Number(result.id);
    }
    if (type === "supplier-product") {
      state.pendingSupplierBindingProductId = Number(result.product_id || 0) || null;
      state.pendingSupplierBindingSupplierId = Number(result.supplier_id || 0) || null;
    }

    state.lookupsLoaded = false;
    form.reset();
    await Promise.all([loadBaseData(), hasModuleAccess("dashboard") ? loadDashboard() : Promise.resolve()]);
  }

  async function handleInboundCreate(form) {
    if (!canDo("create-inbound")) {
      showAlert("当前角色无权限操作", "warning");
      return;
    }

    const currentUser = await ensureActiveUser();
    const values = formValues(form);
    const productId = requireSearchPickerValue("inboundProduct", "请选择有效的入库商品");
    const supplierId = requireSearchPickerValue("inboundSupplier", "请先选择商品，再选择匹配的供应商");
    if (!productId || !supplierId) return;
    const button = form.querySelector('[type="submit"]');
    const result = await runButtonAction(
      button,
      () =>
        API.createInboundOrder({
          supplier_id: supplierId,
          warehouse_id: Number(values.warehouse_id),
          handled_by: Number(currentUser?.id || 0),
          status: "pending",
          remark: optionalValue(values.remark),
          items: [
            {
              product_id: productId,
              quantity: Number(values.quantity),
              batch_no: optionalValue(values.batch_no),
            },
          ],
        }),
      {
        loadingText: "创建中…",
        successMessage: (item) => `入库单 ${item.inbound_no} 已创建`,
      },
    );
    if (!result) return;

    window.bootstrap.Modal.getOrCreateInstance($("createInboundModal")).hide();
    form.reset();
    populateBusinessSelects();
    await loadInbound();
  }

  async function handleRequestCreate(form) {
    if (!canDo("create-replenishment")) {
      showAlert("当前角色无权限操作", "warning");
      return;
    }

    const currentUser = await ensureActiveUser();
    const values = formValues(form);
    const productId = requireSearchPickerValue("requestProduct", "请选择有效的补货商品");
    if (!productId) return;
    const button = form.querySelector('[type="submit"]');
    const result = await runButtonAction(
      button,
      () =>
        API.createReplenishmentRequest({
          store_id: Number(values.store_id),
          product_id: productId,
          request_quantity: Number(values.request_quantity),
          request_reason: optionalValue(values.request_reason),
          created_by: Number(currentUser?.id || 0),
        }),
      {
        loadingText: "提交中…",
        successMessage: (item) => `补货申请 ${item.request_no} 已提交`,
      },
    );
    if (!result) return;

    window.bootstrap.Modal.getOrCreateInstance($("createRequestModal")).hide();
    form.reset();
    populateBusinessSelects();
    await loadFulfillment();
  }

  function showLoginError(message) {
    const errorElement = $("loginError");
    if (!errorElement) return;
    errorElement.textContent = message;
    errorElement.hidden = false;
  }

  function clearLoginError() {
    const errorElement = $("loginError");
    if (!errorElement) return;
    errorElement.hidden = true;
    errorElement.textContent = "";
  }

  function resetInventoryFilters() {
    state.inventoryOverviewPage = 1;
    if ($("inventoryKeywordInput")) $("inventoryKeywordInput").value = "";
    if ($("inventoryLocationTypeFilter")) $("inventoryLocationTypeFilter").value = "all";
    if ($("inventoryLocationFilter")) {
      $("inventoryLocationFilter").innerHTML = '<option value="all">全部仓库与门店</option>';
      $("inventoryLocationFilter").value = "all";
    }
    if ($("inventoryLocationSummary")) {
      $("inventoryLocationSummary").innerHTML = "";
      $("inventoryLocationSummary").hidden = true;
    }
    if ($("inventoryOverviewPagination")) $("inventoryOverviewPagination").hidden = true;
  }

  function resetTransactionFilters() {
    state.transactionPage = 1;
    if ($("transactionKeywordInput")) $("transactionKeywordInput").value = "";
    if ($("transactionWarehouseFilter")) $("transactionWarehouseFilter").innerHTML = '<option value="all">全部仓库</option>';
    if ($("transactionTypeFilter")) $("transactionTypeFilter").innerHTML = '<option value="all">全部类型</option>';
    if ($("transactionSortFilter")) $("transactionSortFilter").value = "desc";
    if ($("transactionPagination")) $("transactionPagination").hidden = true;
  }

  async function enterWorkspace(role, username = role) {
    state.currentRole = role;
    state.currentUser = await resolveCurrentUser(role, username);
    state.currentView = defaultViewForRole();
    state.inventoryTab = "overview";
    state.lookupsLoaded = false;
    state.loadedViews.clear();
    state.loadedInventoryTabs.clear();
    state.inventoryOverviewRows = [];
    state.inventoryWarningRows = [];
    state.transactionsRows = [];
    state.supplierProductsBySupplier.clear();
    state.supplierIdsByProduct.clear();
    state.pendingProductSupplierId = null;
    state.pendingSupplierBindingProductId = null;
    state.pendingSupplierBindingSupplierId = null;
    resetInventoryFilters();
    resetTransactionFilters();

    updateRoleIdentity();
    renderNavigation();
    syncDashboardVisibility();
    applyActionVisibility();

    window.localStorage.setItem("currentRole", role);
    window.localStorage.setItem("currentLoginName", username);
    $("loginScreen").hidden = true;
    $("appShell").hidden = false;

    await initialize();
  }

  function leaveWorkspace() {
    window.localStorage.removeItem("currentRole");
    window.localStorage.removeItem("currentLoginName");
    state.currentRole = null;
    state.currentUser = null;
    state.currentView = "dashboard";
    state.inventoryTab = "overview";
    state.lookupsLoaded = false;
    state.loadedViews.clear();
    state.loadedInventoryTabs.clear();
    state.inventoryOverviewRows = [];
    state.inventoryWarningRows = [];
    state.transactionsRows = [];
    state.supplierProductsBySupplier.clear();
    state.supplierIdsByProduct.clear();
    state.pendingProductSupplierId = null;
    state.pendingSupplierBindingProductId = null;
    state.pendingSupplierBindingSupplierId = null;
    resetInventoryFilters();
    resetTransactionFilters();
    clearAlert();
    updateHistory("");
    closeMobileMenu();
    $("appShell").hidden = true;
    $("loginScreen").hidden = false;
    clearLoginError();
    if ($("loginPassword")) $("loginPassword").value = "demo123";
  }

  async function initialize() {
    renderNavigation();
    syncDashboardVisibility();
    applyActionVisibility();
    clearAlert();

    const requestedView = new URLSearchParams(window.location.search).get("view");
    let deniedMessage = "";
    let initialView = defaultViewForRole();

    if (requestedView && viewLoaders[requestedView]) {
      if (hasModuleAccess(requestedView)) {
        initialView = requestedView;
      } else {
        deniedMessage = `当前角色无权限访问“${moduleLabel(requestedView)}”模块`;
      }
    }

    await switchView(initialView, { force: true });
    if (initialView !== "system") {
      loadSystemStatus().catch(() => {});
    }
    if (deniedMessage) {
      showAlert(deniedMessage, "warning");
    }
  }

  async function handleLoginSubmit(form) {
    const values = formValues(form);
    const button = form.querySelector('[type="submit"]');
    const username = String(values.username || "").trim();
    const password = String(values.password || "").trim();
    const role = String(values.role || "").trim();

    clearLoginError();
    if (!username) {
      showLoginError("请输入用户名");
      return;
    }
    if (!ROLE_LABELS[role]) {
      showLoginError("请选择登录角色");
      return;
    }
    if (password !== "demo123") {
      showLoginError("演示密码统一为 demo123");
      return;
    }

    setButtonLoading(button, true, "登录中…");
    try {
      await enterWorkspace(role, username);
    } catch (error) {
      showLoginError(error?.message || "登录失败，请稍后重试");
    } finally {
      setButtonLoading(button, false);
    }
  }

  function bindEvents() {
    if (state.eventsBound) return;

    $("sideNav").addEventListener("click", async (event) => {
      const button = event.target.closest(".nav-item");
      if (!button) return;
      await switchView(button.dataset.view);
    });

    document.querySelectorAll("[data-jump]").forEach((button) => {
      button.addEventListener("click", async () => {
        await switchView(button.dataset.jump, {
          inventoryTab: button.dataset.jumpTab,
        });
      });
    });

    document.querySelectorAll("[data-inventory-tab]").forEach((button) => {
      button.addEventListener("click", async () => {
        try {
          await switchInventoryTab(button.dataset.inventoryTab, true);
        } catch (error) {
          showAlert(error?.message || "加载库存数据失败");
        }
      });
    });

    $("inventoryKeywordInput")?.addEventListener("input", () => {
      state.inventoryOverviewPage = 1;
      renderInventoryOverview();
    });

    $("inventoryLocationTypeFilter")?.addEventListener("change", () => {
      state.inventoryOverviewPage = 1;
      renderInventoryOverview();
    });

    $("inventoryLocationFilter")?.addEventListener("change", () => {
      state.inventoryOverviewPage = 1;
      renderInventoryOverview();
    });

    $("inventoryPrevPageBtn")?.addEventListener("click", () => {
      setInventoryOverviewPage(state.inventoryOverviewPage - 1);
    });

    $("inventoryNextPageBtn")?.addEventListener("click", () => {
      setInventoryOverviewPage(state.inventoryOverviewPage + 1);
    });

    $("inboundProductSearch")?.addEventListener("input", syncInboundProductPicker);
    $("inboundProductSearch")?.addEventListener("change", syncInboundProductPicker);

    $("inboundSupplierSearch")?.addEventListener("input", syncInboundSupplierPicker);
    $("inboundSupplierSearch")?.addEventListener("change", syncInboundSupplierPicker);

    $("requestProductSearch")?.addEventListener("input", syncRequestProductPicker);
    $("requestProductSearch")?.addEventListener("change", syncRequestProductPicker);

    $("bindProductSearch")?.addEventListener("input", () => {
      const matched = syncSearchPickerSelection(
        "bindProductSearch",
        "bindProduct",
        [...state.products.values()],
        productSearchLabel,
        [(item) => item.name, (item) => item.product_code, (item) => String(item.id)],
      );
      if (matched) {
        $("bindProductSearch").value = productSearchLabel(matched);
      }
    });

    $("bindSupplierSearch")?.addEventListener("input", () => {
      const matched = syncSearchPickerSelection(
        "bindSupplierSearch",
        "bindSupplier",
        [...state.suppliers.values()],
        supplierSearchLabel,
        [(item) => item.name, (item) => String(item.id)],
      );
      if (matched) {
        $("bindSupplierSearch").value = supplierSearchLabel(matched);
      }
    });

    $("productSupplierSearch")?.addEventListener("input", () => {
      const matched = syncSearchPickerSelection(
        "productSupplierSearch",
        "productSupplier",
        [...state.suppliers.values()],
        supplierSearchLabel,
        [(item) => item.name, (item) => String(item.id)],
      );
      if (matched) {
        $("productSupplierSearch").value = supplierSearchLabel(matched);
      }
    });

    ["transactionKeywordInput", "transactionWarehouseFilter", "transactionTypeFilter", "transactionSortFilter"].forEach(
      (id) => {
        $(id)?.addEventListener(id === "transactionKeywordInput" ? "input" : "change", () => {
          state.transactionPage = 1;
          renderTransactions();
        });
      },
    );

    $("transactionPrevPageBtn")?.addEventListener("click", () => {
      setTransactionPage(state.transactionPage - 1);
    });

    $("transactionNextPageBtn")?.addEventListener("click", () => {
      setTransactionPage(state.transactionPage + 1);
    });

    document.querySelectorAll(".module-refresh").forEach((button) => {
      button.addEventListener("click", () => refreshView(button.dataset.loader, button));
    });

    $("refreshCurrentBtn").addEventListener("click", (event) =>
      refreshView(state.currentView, event.currentTarget),
    );

    $("generateRecommendationBtn").addEventListener("click", async (event) => {
      if (!canDo("generate-recommendations")) {
        showAlert("当前角色无权限操作", "warning");
        showToast("当前角色无权限操作", "error");
        return;
      }
      await runButtonAction(
        event.currentTarget,
        async () => {
          const result = await API.generateRecommendations();
          await Promise.all([
            loadRecommendations(),
            hasModuleAccess("dashboard") ? loadDashboard() : Promise.resolve(),
          ]);
          return result;
        },
        {
          loadingText: "生成中…",
          successMessage: (result) => `已生成 ${formatNumber(result.count)} 条补货建议`,
        },
      );
    });

    document.querySelectorAll("[data-create-form]").forEach((form) => {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await handleBaseDataCreate(event.currentTarget);
      });
    });

    $("productForm")?.addEventListener("reset", () => {
      window.setTimeout(() => populateBusinessSelects(), 0);
    });

    $("createInboundForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await handleInboundCreate(event.currentTarget);
    });

    $("createInboundForm").addEventListener("reset", () => {
      window.setTimeout(() => populateBusinessSelects(), 0);
    });

    $("createRequestForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await handleRequestCreate(event.currentTarget);
    });

    $("createRequestForm").addEventListener("reset", () => {
      window.setTimeout(() => populateBusinessSelects(), 0);
    });

    $("supplierProductForm")?.addEventListener("reset", () => {
      window.setTimeout(() => populateBusinessSelects(), 0);
    });

    document.addEventListener("click", (event) => {
      const actionButton = event.target.closest(".row-action");
      if (actionButton) {
        handleRowAction(actionButton);
      }
    });

    $("mobileMenuBtn").addEventListener("click", () => {
      const sidebar = $("appSidebar");
      const willOpen = !sidebar.classList.contains("is-open");
      sidebar.classList.toggle("is-open", willOpen);
      $("mobileMenuBtn").setAttribute("aria-expanded", String(willOpen));
    });

    $("logoutBtn").addEventListener("click", leaveWorkspace);
    $("loginForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      await handleLoginSubmit(event.currentTarget);
    });

    window.addEventListener("resize", () => {
      state.charts.forEach((chart) => chart.resize());
      if (window.innerWidth > 900) closeMobileMenu();
    });

    state.eventsBound = true;
  }

  async function bootstrap() {
    bindEvents();
    const savedRole = window.localStorage.getItem("currentRole");
    const savedName = window.localStorage.getItem("currentLoginName") || "demo";
    $("loginScreen").hidden = false;
    $("appShell").hidden = true;

    if (savedRole && ROLE_LABELS[savedRole]) {
      if ($("loginRole")) $("loginRole").value = savedRole;
      if ($("loginUsername")) $("loginUsername").value = savedName;
    }
  }

  bootstrap();
})();
