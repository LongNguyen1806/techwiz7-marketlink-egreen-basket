# MarketLink — Farm Fresh Just a Click Away

**Theme:** eGreen Basket | **Category:** End-to-End Web Solutions (TechWiz 7)

MarketLink is a full-stack web application that connects local farmers-market producers with community shoppers. Farmers publish their weekly stock, pricing, operating days, and market pickup slots; customers discover nearby markets and stalls on an interactive map, place pre-orders for pickup, and leave verified reviews; administrators oversee farmer approvals, market schedules, content moderation, and platform analytics.

---

## 1. Technology Stack & Architecture

- **Frontend:** React 19, Vite, Tailwind CSS, Zustand, React Router v7, Leaflet / OpenStreetMap
- **Backend:** Python 3.11+, Django 5.2, Django REST Framework, SimpleJWT (HttpOnly Cookie + Bearer Auth), Django Channels & Daphne (WebSocket Real-Time Notifications)
- **Database:** MySQL 8.0+ (`InnoDB`, `utf8mb4`) — 27 core domain tables + 8 historical audit tables (`django-simple-history`)
- **AI & Geolocation Integrations:** OpenStreetMap / Nominatim / OSRM (interactive maps, pins & routing) and Google Gemini API (`gemini-2.5-flash` for the optional AI Marketplace Assistant and automated listing moderation, with deterministic rule-based fallback)

---

## 2. Project Assumptions (Per SRS Section 1.5 & 1.9)

1. **In-Person Cash Settlement Only:** In accordance with SRS Section 1.5, online payment gateways and courier/delivery logistics are out of scope. All pre-orders are reserved online and paid for in person (cash at pickup) at the farmer's market stall.
2. **Order Grouping per Stall & Market Slot:** Because each farmer manages independent inventory, cut-off times, and pickup windows at specific markets, a multi-stall shopping cart automatically generates one separate pre-order per farmer stall at checkout.
3. **Order Cut-Off & Two-Phase Modification:** Customers can freely edit or cancel a pre-order while its status is `PLACED` and before the farmer's configured cut-off window (`order_cutoff_hours`, default 12 hours before pickup). Once a farmer has `ACCEPTED` an order, customer edits before cut-off are submitted as a structured **Change Request** for the farmer to approve or reject.
4. **Unapproved Farmer Sandbox:** Newly registered farmers (`PENDING` status) can sign in to complete their stall profile and track their market application, but cannot publish products to the public catalog until approved by an Administrator (SRS Section 1.6).
5. **Verified Buyer Reviews:** Only customers who have a `COMPLETED` order with a stall/product can submit a 1–5 star rating and review (one stall review per completed order and one product review per order line item).
6. **Currency & Language:** All user interfaces, notifications, and sample data are standardized in English with prices denominated in USD (`$`).
7. **AI Graceful Degradation:** If no `GEMINI_API_KEY` is configured in the evaluation environment, both the AI Chatbot Assistant and the AI Listing Moderation engine automatically fall back to deterministic database/rule-based engines so all features function 100% offline without external API keys.

---

## 3. Project Installation Instructions (MANDATORY)

### Prerequisites

- **Python:** 3.11 or higher
- **Node.js:** 18.x or 20.x LTS (with `npm`)
- **Database:** MySQL Server 8.0+ running on `localhost:3306`

### Step 1: Database Setup (MySQL 8.0+)

You can initialize the database using **either** the provided SQL dump (`marketlink_mysql.sql`) **or** Django migrations + seed command:

**Option A — Import SQL Script Directly:**

```sql
mysql -u root -p < marketlink_mysql.sql
```

*(This script automatically creates the `marketlink` database, all tables, constraints, indexes, and pre-loads the complete evaluation dataset).*

**Option B — Create Empty Database & Run Django Seed Command:**

```sql
CREATE DATABASE IF NOT EXISTS `marketlink` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

### Step 2: Backend Setup (Django API & WebSocket Server)

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # (or cp .env.example .env on macOS/Linux)
```

Update `backend/.env` with your local MySQL credentials:

```env
DB_NAME=marketlink
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
USE_REDIS=False
```

Run migrations and seed realistic evaluation data (if you used Option B in Step 1):

```bash
python manage.py migrate
python manage.py seed_real_data
```

Start the backend server on `http://localhost:8000`:

```bash
python manage.py runserver 0.0.0.0:8000
```

- **Swagger / OpenAPI Documentation:** `http://localhost:8000/api/docs/`

### Step 3: Frontend Setup (React + Vite)

Open a new terminal window:

```bash
cd frontend
npm install
npm run dev
```

- **Web Application URL:** `http://localhost:5173`
*(Vite automatically proxies `/api`, `/media`, and `/ws` requests to `http://localhost:8000`).*

---

## 4. User Credentials for Evaluation (MANDATORY)

Every pre-seeded account across all roles uses the unified password: **`Pass@123`**

### 4.1. Administrator Account

- **Sign-In URL:** `http://localhost:5173/admin/login`

| Role | Email | Password | Description |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@marketlink.com` | `Pass@123` | Full platform governance, approvals, markets, moderation, reports & system config |

### 4.2. Farmer Accounts (Approved & Pending Stalls)

- **Sign-In URL:** `http://localhost:5173/login`

| Role / Status | Email | Password | Stall Name & Assigned Market |
| :--- | :--- | :--- | :--- |
| **Farmer (Approved)** | `farmer_01@marketlink.com` | `Pass@123` | **Hoc Mon Agri Supply** — Binh Dien Wholesale Market |
| **Farmer (Approved)** | `farmer_02@marketlink.com` | `Pass@123` | **Thu Duc Fresh Organics** — Thu Duc Wholesale Agricultural Market |
| **Farmer (Approved)** | `farmer_03@marketlink.com` | `Pass@123` | **Binh Dien Farm Direct** — Binh Dien Wholesale Market |
| **Farmer (Approved)** | `farmer_04@marketlink.com` | `Pass@123` | **Ba Chieu Market Garden** — Ba Chieu Market |
| **Farmer (Approved)** | `farmer_05@marketlink.com` | `Pass@123` | **Cho Lon Spices & Grains** — Binh Tay Market (Cho Lon) |
| **Farmer (Approved)** | `farmer_06@marketlink.com` | `Pass@123` | **Tan Dinh Select Produce** — Tan Dinh Market |
| **Farmer (Pending Approval)** | `farmer_07@marketlink.com` | `Pass@123` | **Cu Chi Green Leaf Farm** — Waiting for Admin Approval Sandbox |
| **Farmer (Pending Approval)** | `farmer_08@marketlink.com` | `Pass@123` | **Can Gio Coastal Produce** — Waiting for Admin Approval Sandbox |

### 4.3. Customer (Shopper) Accounts

- **Sign-In URL:** `http://localhost:5173/login`

| Role / Status | Email | Password | Notes |
| :--- | :--- | :--- | :--- |
| **Customer (Primary Demo)** | `customer_01@marketlink.com` | `Pass@123` | Active pre-orders, completed orders ready for review, saved favorites |
| **Customer (Active)** | `customer_02@marketlink.com` → `customer_18@marketlink.com` | `Pass@123` | 17 additional shoppers with realistic order & review histories |
| **Customer (At-Risk / No-Show)** | `customer_19@marketlink.com`, `customer_20@marketlink.com` | `Pass@123` | Flagged with 3 missed pickups (no-shows) in the last 30 days for Admin review |

---

## 5. Summary of Core SRS & Extended Bonus Features

- **Core SRS Features Implemented (100%):**
  - Role-based registration & login (`Customer`, `Farmer`, dedicated `Admin` portal).
  - Interactive OpenStreetMap / Leaflet market & stall discovery with GPS "Near me" filtering and route directions.
  - Product catalog search & filtering by category, price range, market location, and operating day.
  - Pre-order cart & pickup slot checkout, order modification/cancellation before cut-off, quick reorder, favorites with automatic restock alerts, and verified product/stall reviews with farmer replies.
  - Farmer recurring weekly stock template, bulk stock controls, order fulfillment queue, and sales insights.
  - Admin dashboard KPIs, farmer/customer account management, market CRUD, content moderation, categories, announcements, and platform-wide reports.
- **Extended Value-Add / Bonus Features:**
  - **Hybrid AI Listing Moderation & Audit Queue (`/admin/approvals?tab=ai`):** Combines Google Gemini Vision/Text evaluation with heuristic rule checks to auto-approve clean listings and hold policy violations.
  - **Category Price & Stock Anomaly Guidelines (`/admin/categories?guidelines=open`):** Automatically flags suspicious pricing or stock quantities per category and unit.
  - **Dynamic Anti-Abuse Platform Limits (`/admin/limits`):** Configurable limits on open pre-orders, items per order, and no-show strikes.
  - **Immutable Security Audit Trail (`/admin/audit-logs`) & Read-Only Support Order Inspector (`/admin/orders`).**
  - **Context-Aware AI Marketplace Assistant:** Floating chatbot answering live questions using real-time database inventory and market schedules.

---

## 6. Acknowledgement of AI Tools Used (Per SRS Page 13)

In compliance with the SRS disclosure guidelines, the following AI-assisted tools were used as supporting aids during development:

- **Google Gemini API (`gemini-2.5-flash`):** Integrated into the application backend for the optional AI Customer Assistant chatbot and automated product listing/review moderation.
- **AI Coding Assistants (GitHub Copilot / Gemini Code Assist):** Used as productivity aids for boilerplate generation, debugging, and test case scaffolding. All system architecture, database modeling, business logic, and final implementations were designed, verified, and customized by the development team.
