CREATE TABLE categories (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	parent_id INTEGER, 
	description VARCHAR(255), 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_category_name_parent UNIQUE (name, parent_id), 
	FOREIGN KEY(parent_id) REFERENCES categories (id)
);

CREATE TABLE distributed_sync_logs (
	id INTEGER NOT NULL, 
	node_name VARCHAR(100) NOT NULL, 
	node_type VARCHAR(50) NOT NULL, 
	region VARCHAR(50), 
	sync_type VARCHAR(50) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	checked_records INTEGER NOT NULL, 
	mismatch_records INTEGER NOT NULL, 
	started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	finished_at DATETIME, 
	message VARCHAR(255), 
	PRIMARY KEY (id)
);

CREATE TABLE stores (
	id INTEGER NOT NULL, 
	store_code VARCHAR(50) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	region VARCHAR(50), 
	address VARCHAR(255), 
	longitude FLOAT, 
	latitude FLOAT, 
	contact_person VARCHAR(100), 
	phone VARCHAR(50), 
	business_status VARCHAR(30) NOT NULL, 
	is_synthetic BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (store_code)
);

CREATE TABLE suppliers (
	id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	contact_person VARCHAR(100), 
	phone VARCHAR(50) NOT NULL, 
	email VARCHAR(100), 
	address VARCHAR(255), 
	supplier_level VARCHAR(10), 
	cooperation_status VARCHAR(30) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE warehouses (
	id INTEGER NOT NULL, 
	warehouse_code VARCHAR(50) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	address VARCHAR(255), 
	manager_name VARCHAR(100), 
	phone VARCHAR(50), 
	max_capacity INTEGER, 
	status VARCHAR(30) NOT NULL, 
	region VARCHAR(50), 
	is_synthetic BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (warehouse_code)
);

CREATE TABLE products (
	id INTEGER NOT NULL, 
	product_code VARCHAR(50) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	barcode VARCHAR(50), 
	category_id INTEGER, 
	spec VARCHAR(100), 
	unit VARCHAR(20) NOT NULL, 
	shelf_life_days INTEGER, 
	default_safety_stock INTEGER NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (product_code), 
	UNIQUE (barcode), 
	FOREIGN KEY(category_id) REFERENCES categories (id)
);

CREATE TABLE supplier_score_snapshots (
	id INTEGER NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	product_count INTEGER NOT NULL, 
	avg_lead_time_days FLOAT NOT NULL, 
	total_purchase_amount NUMERIC(12, 2) NOT NULL, 
	delayed_arrival_count INTEGER NOT NULL, 
	score FLOAT NOT NULL, 
	score_source VARCHAR(50) NOT NULL, 
	generated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id)
);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(50) NOT NULL, 
	employee_no VARCHAR(50) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	verification_code_hash VARCHAR(255) NOT NULL, 
	real_name VARCHAR(100), 
	role VARCHAR(50) NOT NULL, 
	location_type VARCHAR(20), 
	warehouse_id INTEGER, 
	store_id INTEGER, 
	phone VARCHAR(50), 
	is_active BOOLEAN NOT NULL, 
	is_verified BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username), 
	UNIQUE (employee_no), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id)
);

CREATE TABLE ai_recommendations (
	id INTEGER NOT NULL, 
	store_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	current_stock INTEGER NOT NULL, 
	recent_7_sales FLOAT NOT NULL, 
	recent_30_sales FLOAT NOT NULL, 
	avg_daily_sales FLOAT NOT NULL, 
	safety_stock INTEGER NOT NULL, 
	recommended_quantity INTEGER NOT NULL, 
	recommended_supplier_id INTEGER, 
	shortage_risk BOOLEAN NOT NULL, 
	risk_level VARCHAR(20) NOT NULL, 
	days_until_stockout FLOAT NOT NULL, 
	reason VARCHAR(500) NOT NULL, 
	reason_enhanced VARCHAR(1000), 
	llm_provider VARCHAR(30) NOT NULL, 
	llm_used BOOLEAN NOT NULL, 
	generated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	adoption_status VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(recommended_supplier_id) REFERENCES suppliers (id)
);

CREATE TABLE cross_warehouse_transfer_orders (
	id INTEGER NOT NULL, 
	transfer_no VARCHAR(50) NOT NULL, 
	source_warehouse_id INTEGER NOT NULL, 
	target_warehouse_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	completed_at DATETIME, 
	created_by INTEGER, 
	reason VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (transfer_no), 
	FOREIGN KEY(source_warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(target_warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE inventory (
	id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	location_type VARCHAR(20) NOT NULL, 
	warehouse_id INTEGER, 
	store_id INTEGER, 
	current_quantity INTEGER NOT NULL, 
	frozen_quantity INTEGER NOT NULL, 
	safety_stock INTEGER NOT NULL, 
	max_stock INTEGER NOT NULL, 
	last_updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_inventory_product_warehouse UNIQUE (product_id, warehouse_id), 
	CONSTRAINT uq_inventory_product_store UNIQUE (product_id, store_id), 
	CONSTRAINT ck_inventory_current_nonnegative CHECK (current_quantity >= 0), 
	CONSTRAINT ck_inventory_frozen_nonnegative CHECK (frozen_quantity >= 0), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id)
);

CREATE TABLE monthly_sales_facts (
	id INTEGER NOT NULL, 
	year INTEGER NOT NULL, 
	month INTEGER NOT NULL, 
	supplier_id INTEGER, 
	product_id INTEGER NOT NULL, 
	category_id INTEGER, 
	retail_sales FLOAT NOT NULL, 
	retail_transfers FLOAT NOT NULL, 
	warehouse_sales FLOAT NOT NULL, 
	store_id INTEGER, 
	warehouse_id INTEGER, 
	promo_flag BOOLEAN NOT NULL, 
	is_example_data BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id)
);

CREATE TABLE promotions (
	id INTEGER NOT NULL, 
	promotion_name VARCHAR(120) NOT NULL, 
	start_date DATE, 
	end_date DATE, 
	store_id INTEGER, 
	product_id INTEGER, 
	category_id INTEGER, 
	promo_factor FLOAT NOT NULL, 
	description VARCHAR(255), 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id)
);

CREATE TABLE purchase_orders (
	id INTEGER NOT NULL, 
	order_no VARCHAR(50) NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	created_by INTEGER NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	expected_arrival_date DATE, 
	status VARCHAR(30) NOT NULL, 
	total_amount NUMERIC(12, 2) NOT NULL, 
	remark VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (order_no), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE replenishment_requests (
	id INTEGER NOT NULL, 
	request_no VARCHAR(50) NOT NULL, 
	store_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	request_quantity INTEGER NOT NULL, 
	request_reason VARCHAR(255), 
	request_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	audit_status VARCHAR(30) NOT NULL, 
	audited_by INTEGER, 
	audit_time DATETIME, 
	created_by INTEGER, 
	generated_outbound_order_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (request_no), 
	FOREIGN KEY(store_id) REFERENCES stores (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(audited_by) REFERENCES users (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE TABLE stock_transactions (
	id INTEGER NOT NULL, 
	transaction_no VARCHAR(50) NOT NULL, 
	product_id INTEGER NOT NULL, 
	transaction_type VARCHAR(50) NOT NULL, 
	source_location_type VARCHAR(20), 
	source_warehouse_id INTEGER, 
	source_store_id INTEGER, 
	target_location_type VARCHAR(20), 
	target_warehouse_id INTEGER, 
	target_store_id INTEGER, 
	change_quantity INTEGER NOT NULL, 
	before_quantity INTEGER, 
	after_quantity INTEGER, 
	transaction_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	operated_by INTEGER, 
	related_doc_type VARCHAR(50), 
	related_doc_id INTEGER, 
	remark VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (transaction_no), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(source_warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(source_store_id) REFERENCES stores (id), 
	FOREIGN KEY(target_warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(target_store_id) REFERENCES stores (id), 
	FOREIGN KEY(operated_by) REFERENCES users (id)
);

CREATE TABLE supplier_products (
	id INTEGER NOT NULL, 
	supplier_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	supply_price NUMERIC(12, 2) NOT NULL, 
	lead_time_days INTEGER NOT NULL, 
	on_time_rate FLOAT NOT NULL, 
	quality_score FLOAT NOT NULL, 
	is_preferred BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_supplier_product UNIQUE (supplier_id, product_id), 
	CONSTRAINT ck_supplier_product_lead_time_nonnegative CHECK (lead_time_days >= 0), 
	CONSTRAINT ck_supplier_product_quality CHECK (quality_score >= 0 AND quality_score <= 10), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE inbound_orders (
	id INTEGER NOT NULL, 
	inbound_no VARCHAR(50) NOT NULL, 
	purchase_order_id INTEGER, 
	supplier_id INTEGER NOT NULL, 
	warehouse_id INTEGER NOT NULL, 
	inbound_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	handled_by INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	remark VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (inbound_no), 
	FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders (id), 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id), 
	FOREIGN KEY(warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(handled_by) REFERENCES users (id)
);

CREATE TABLE outbound_orders (
	id INTEGER NOT NULL, 
	outbound_no VARCHAR(50) NOT NULL, 
	source_warehouse_id INTEGER NOT NULL, 
	target_store_id INTEGER NOT NULL, 
	outbound_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	handled_by INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	source_request_id INTEGER, 
	remark VARCHAR(255), 
	PRIMARY KEY (id), 
	UNIQUE (outbound_no), 
	FOREIGN KEY(source_warehouse_id) REFERENCES warehouses (id), 
	FOREIGN KEY(target_store_id) REFERENCES stores (id), 
	FOREIGN KEY(handled_by) REFERENCES users (id), 
	FOREIGN KEY(source_request_id) REFERENCES replenishment_requests (id)
);

CREATE TABLE purchase_order_items (
	id INTEGER NOT NULL, 
	purchase_order_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	purchase_quantity INTEGER NOT NULL, 
	purchase_price NUMERIC(12, 2) NOT NULL, 
	subtotal_amount NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE inbound_items (
	id INTEGER NOT NULL, 
	inbound_order_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	batch_no VARCHAR(50), 
	production_date DATE, 
	expiry_date DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(inbound_order_id) REFERENCES inbound_orders (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);

CREATE TABLE outbound_items (
	id INTEGER NOT NULL, 
	outbound_order_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	batch_no VARCHAR(50), 
	PRIMARY KEY (id), 
	FOREIGN KEY(outbound_order_id) REFERENCES outbound_orders (id), 
	FOREIGN KEY(product_id) REFERENCES products (id)
);
