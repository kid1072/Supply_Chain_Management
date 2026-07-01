(function () {
  "use strict";

  const API_BASE = "/api";
  const REQUEST_TIMEOUT = 15000;

  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT);
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
        signal: options.signal || controller.signal,
      });
      const json = await response.json().catch(() => null);

      if (!response.ok || !json?.success) {
        throw new Error(json?.message || `请求失败（HTTP ${response.status}）`);
      }
      return json.data;
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("请求超时，请检查后端服务");
      }
      if (error instanceof TypeError) {
        throw new Error("无法连接后端，请确认服务已启动");
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  function get(path) {
    return request(path);
  }

  function withQuery(path, params = {}) {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        search.set(key, String(value));
      }
    });
    const query = search.toString();
    return query ? `${path}?${query}` : path;
  }

  function extractItems(data) {
    if (Array.isArray(data)) {
      return { items: data, total: data.length, page: 1, page_size: data.length };
    }
    return {
      items: Array.isArray(data?.items) ? data.items : [],
      total: Number(data?.total || 0),
      page: Number(data?.page || 1),
      page_size: Number(data?.page_size || 0),
    };
  }

  async function getAllPages(path, options = {}) {
    const pageSize = Number(options.pageSize || 100);
    const firstPage = extractItems(await get(withQuery(path, { page: 1, page_size: pageSize })));
    const totalPages =
      firstPage.page_size > 0 ? Math.max(1, Math.ceil(firstPage.total / firstPage.page_size)) : 1;
    const items = [...firstPage.items];

    for (let page = 2; page <= totalPages; page += 1) {
      const nextPage = extractItems(await get(withQuery(path, { page, page_size: pageSize })));
      items.push(...nextPage.items);
    }

    return items;
  }

  function post(path, body) {
    return request(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  }

  const api = {
    request,
    getHealth: () => get("/health"),
    getDatabaseHealth: () => get("/health/db"),
    getExampleStatus: () => get("/example/status"),
    getDashboard: () => get("/analytics/dashboard"),
    getInventoryRanking: () => get("/analytics/inventory-ranking"),
    getWarehouseFlowTrend: () => get("/analytics/warehouse-flow-trend"),
    getWarnings: () => get("/inventory/warnings"),
    getInventory: () => getAllPages("/inventory", { pageSize: 100 }),
    getInboundOrders: () => get("/inbound-orders?page=1&page_size=100"),
    completeInbound: (orderId) => post(`/inbound-orders/${orderId}/complete`),
    getReplenishmentRequests: () => get("/replenishment-requests?page=1&page_size=100"),
    approveReplenishment: (requestId, auditedBy) =>
      post(`/replenishment-requests/${requestId}/approve?audited_by=${encodeURIComponent(auditedBy)}`),
    rejectReplenishment: (requestId, auditedBy) =>
      post(`/replenishment-requests/${requestId}/reject?audited_by=${encodeURIComponent(auditedBy)}`),
    convertReplenishment: (requestId, handledBy) =>
      post(`/replenishment-requests/${requestId}/convert-to-outbound?handled_by=${encodeURIComponent(handledBy)}`),
    getOutboundOrders: () => get("/outbound-orders?page=1&page_size=100"),
    shipOutbound: (orderId) => post(`/outbound-orders/${orderId}/ship`),
    signOutbound: (orderId) => post(`/outbound-orders/${orderId}/sign`),
    getTransactions: () => getAllPages("/transactions", { pageSize: 100 }),
    generateRecommendations: () => post("/recommendations/generate"),
    getRecommendations: () => get("/recommendations"),
    getSupplierRanking: () => get("/suppliers/ranking"),
    getUsers: () => get("/users?page=1&page_size=200"),
    getProducts: () => get("/products?page=1&page_size=200"),
    createProduct: (payload) => post("/products", payload),
    getSuppliers: () => get("/suppliers?page=1&page_size=200"),
    getSupplierProducts: (supplierId) => get(`/suppliers/${supplierId}/products`),
    bindSupplierProduct: (supplierId, payload) => post(`/suppliers/${supplierId}/products`, payload),
    createSupplier: (payload) => post("/suppliers", payload),
    getWarehouses: () => get("/warehouses?page=1&page_size=100"),
    createWarehouse: (payload) => post("/warehouses", payload),
    getStores: () => get("/stores?page=1&page_size=200"),
    createStore: (payload) => post("/stores", payload),
    createInboundOrder: (payload) => post("/inbound-orders", payload),
    createReplenishmentRequest: (payload) => post("/replenishment-requests", payload),
  };

  window.SupplyAPI = Object.freeze(api);
})();
