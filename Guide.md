# MarketLink — Installation Guide

This guide explains how to install and run MarketLink on a local computer, and lists the sign-in details for every type of user.

MarketLink has two parts that run side by side:

| Part | Technology | Address when running |
| :--- | :--- | :--- |
| Backend (API) | Python, Django, MySQL | `http://localhost:8000` |
| Frontend (website) | React, Vite | `http://localhost:5173` |

---

## 1. Requirements

Install these before you start:

| Software | Version | Notes |
| :--- | :--- | :--- |
| Python | 3.10 or newer | Tested with 3.14 |
| MySQL Community Server | 8.x | InnoDB, character set `utf8mb4` |
| Node.js | 20.19+ or 22.12+ | Tested with 22.19; npm comes with it |
| Git | any recent version | Only needed to download the code |
| Redis | optional | Not needed for local use |

An internet connection is needed for the map tiles (OpenStreetMap), address lookup (Nominatim) and the optional AI features.

---

## 2. Get the code

Download or clone the project, then open a terminal in the project folder `MarketLink-Project`. It contains the folders `backend` and `frontend`.

---

## 3. Create the database

Open MySQL (MySQL Workbench or the `mysql` command line) and create an empty database:

```sql
CREATE DATABASE marketlink_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

The tables are created in step 4.4, so nothing else needs to be done in MySQL.

---

## 4. Set up the backend

All commands in this section are run inside the `backend` folder.

### 4.1 Create a virtual environment and install the packages

**Windows**

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux**

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4.2 Create the configuration file

Copy the example file:

- Windows: `copy .env.example .env`
- macOS / Linux: `cp .env.example .env`

Open `backend/.env` and set the database connection:

| Setting | What to enter |
| :--- | :--- |
| `DB_NAME` | `marketlink_db` (the database from step 3) |
| `DB_USER` | Your MySQL user, e.g. `root` |
| `DB_PASSWORD` | Your MySQL password |
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `3306` unless MySQL runs elsewhere |
| `DEBUG` | Keep `True` for local use |

All other settings can stay as they are for a local installation. Optional features are described in section 7.

### 4.3 Check the configuration

```bash
python manage.py check
```

The result should be `System check identified no issues`.

### 4.4 Create the tables

```bash
python manage.py migrate
```

This creates every table and the three user roles (Admin, Farmer, Customer).

### 4.5 Load the sample data

```bash
python manage.py seed_real_data
```

This loads a complete demo: markets in Ho Chi Minh City, farmers with stalls and pickup slots, about 80 products, 20 customers, five months of orders and reviews, listings waiting for review, and price guidelines. The accounts it creates are listed in section 6.

> Running this command again deletes all existing data and loads the demo again from the start.

### 4.6 Start the backend

```bash
python manage.py runserver
```

Leave this terminal open. The API is now available at `http://localhost:8000`.

---

## 5. Set up the frontend

Open a **second terminal** in the project folder and run:

```bash
cd frontend
npm install
npm run dev
```

Leave this terminal open as well. Open **`http://localhost:5173`** in a browser to use MarketLink.

The frontend forwards all API, image and real-time requests to the backend on port 8000, so both terminals must stay open.

---

## 6. User credentials

Every sample account uses the same password: **`Pass@123`**

### Administrator

| Email | Password | Sign-in page |
| :--- | :--- | :--- |
| `admin@marketlink.com` | `Pass@123` | `http://localhost:5173/admin/login` |

### Farmers (approved, selling)

Sign in at `http://localhost:5173/login`.

| Email | Password | Stall |
| :--- | :--- | :--- |
| `farmer_01@marketlink.com` | `Pass@123` | Thu Duc Fresh Organics |
| `farmer_02@marketlink.com` | `Pass@123` | Hoc Mon Agri Supply |
| `farmer_03@marketlink.com` | `Pass@123` | Binh Dien Farm Direct |
| `farmer_04@marketlink.com` | `Pass@123` | Ba Chieu Market Garden |
| `farmer_05@marketlink.com` | `Pass@123` | Cho Lon Spices & Grains |
| `farmer_06@marketlink.com` | `Pass@123` | Tan Dinh Select Produce |

### Farmers (waiting for administrator approval)

These two accounts show the approval flow: they can sign in but cannot sell until an administrator approves them.

| Email | Password | Stall |
| :--- | :--- | :--- |
| `farmer_07@marketlink.com` | `Pass@123` | Cu Chi Green Leaf Farm |
| `farmer_08@marketlink.com` | `Pass@123` | Can Gio Coastal Produce |

### Customers

Sign in at `http://localhost:5173/login`.

| Email | Password | Notes |
| :--- | :--- | :--- |
| `customer_01@marketlink.com` … `customer_18@marketlink.com` | `Pass@123` | Regular customers with order history |
| `customer_19@marketlink.com`, `customer_20@marketlink.com` | `Pass@123` | Customers with several missed pickups ("no-show"), for the at-risk list in the admin area |

New customer and farmer accounts can also be created from the **Sign up** pages. Administrator accounts cannot be created from the website; use the sample account above or run `python manage.py createsuperuser` in the `backend` folder.

---

## 7. Optional features

MarketLink works fully without the settings below. Add them to `backend/.env` only if you want these features, then restart the backend.

| Feature | Settings | Without it |
| :--- | :--- | :--- |
| AI chat assistant and AI listing review | `GEMINI_API_KEY` (a Google Gemini API key) | The chat assistant is unavailable; new listings are checked by rules only and wait for an administrator |
| Real emails (order confirmations, ready for pickup) | `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (a Gmail app password) | Emails are printed in the backend terminal instead of being sent |
| Address lookup on the map | `NOMINATIM_USER_AGENT`, e.g. `MarketLink/1.0 (your-email@example.com)` | Lookups still work but may be refused by the free service more often |
| Redis (several server processes, production) | `USE_REDIS=True`, `REDIS_URL` | Not needed on one computer |

---

## 8. Troubleshooting

| Problem | Solution |
| :--- | :--- |
| `Access denied for user` or `Unknown database` during `migrate` | Check `DB_USER`, `DB_PASSWORD` and `DB_NAME` in `backend/.env`, and that the database from step 3 exists |
| `accounts.E001 Token revocation needs a shared Redis cache` | `DEBUG` is `False`. Set `DEBUG=True` for local use, or set up Redis (section 7) |
| `SECRET_KEY must be set when DEBUG is False` | Same cause: set `DEBUG=True` for local use |
| The website opens but shows no data or cannot sign in | The backend is not running. Start it with `python manage.py runserver` (step 4.6) |
| Port 8000 or 5173 is already in use | Close the other program using the port, or stop an older MarketLink terminal |
| `npm install` fails | Check the Node.js version with `node --version` (see section 1) |
| Sample data looks wrong after testing | Run `python manage.py seed_real_data` again to reset it |

---

## 9. Quick start (summary)

1. Create the MySQL database `marketlink_db`.
2. In `backend`: create the virtual environment, run `pip install -r requirements.txt`, copy `.env.example` to `.env` and fill in the database settings.
3. In `backend`: run `python manage.py migrate`, then `python manage.py seed_real_data`, then `python manage.py runserver`.
4. In `frontend`: run `npm install`, then `npm run dev`.
5. Open `http://localhost:5173` and sign in with an account from section 6 (password `Pass@123`).
