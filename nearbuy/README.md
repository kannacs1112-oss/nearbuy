# NEARBUY — Local Marketplace Prototype

NEARBUY is a Flask-powered hyperlocal marketplace prototype for discovering neighbourhood shops, browsing products, placing demo orders and coordinating local delivery.

## Features
- City-based shop discovery (demo data seeded for Madurai)
- Shop categories, shop profiles, owners and product catalogues
- Customer registration, login, cart, checkout and order history
- Shopkeeper registration, admin approval, product and order management
- Delivery partner dashboard with pickup claiming and status updates
- Admin console with shop approvals and platform metrics
- Keyword-based smart product discovery (clearly labelled prototype feature)
- SQLite for quick local setup; MySQL supported through `DATABASE_URL`

## Requirements
- Python 3.10+
- pip
- Optional: MySQL 8+ for a shared deployment database

## Run on Windows (PowerShell or CMD)
1. Extract `NEARBUY.zip`.
2. Open a terminal in the extracted `nearbuy` folder.
3. Create a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```
4. Install packages:

   ```powershell
   py -m pip install -r requirements.txt
   ```
5. Start the app:

   ```powershell
   py app.py
   ```
6. Open `http://127.0.0.1:5000`.

The app creates `nearbuy.db` and inserts Madurai demo listings automatically on first launch.

## Demo accounts
| Role | Email | Password |
|---|---|---|
| Admin | admin@nearbuy.demo | Admin@123 |
| Customer | customer@nearbuy.demo | Customer@123 |
| Shopkeeper | shop@nearbuy.demo | Shop@123 |
| Delivery partner | delivery@nearbuy.demo | Delivery@123 |

Change these credentials and the secret key before any public deployment. These are demonstration credentials only.

## MySQL setup (optional)
1. Create a database and user in MySQL:

   ```sql
   CREATE DATABASE nearbuy CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'nearbuy_user'@'localhost' IDENTIFIED BY 'your_password';
   GRANT ALL PRIVILEGES ON nearbuy.* TO 'nearbuy_user'@'localhost';
   FLUSH PRIVILEGES;
   ```
2. Copy `.env.example` to `.env` and set:

   ```env
   DATABASE_URL=mysql+pymysql://nearbuy_user:your_password@localhost/nearbuy?charset=utf8mb4
   SECRET_KEY=replace-with-a-long-random-secret
   ```
3. Restart the app. SQLAlchemy creates the tables automatically.

## Important prototype notes
- Demo shop names, owners, phone numbers and product listings are fictional sample data. Replace them with verified business information and obtain consent before publishing real owner/contact details.
- Checkout is simulated and marked as demo/cash-on-delivery. No real payment gateway is connected.
- AI discovery currently uses keyword matching against the catalogue. It is not a generative AI model yet.
- Delivery assignment and statuses are functional in the local prototype, but live GPS tracking, maps routing, push notifications and automated dispatch are future enhancements.
- For production: add CSRF protection, email/phone verification, rate limiting, audit logs, migrations, backups, privacy policy, payment provider integration and deployment secrets management.
- Prototype checkout is limited to one shop per order. This keeps inventory and delivery assignment straightforward for the first version.

## Main project structure
```
nearbuy/
├── app.py
├── config.py
├── models.py
├── requirements.txt
├── .env.example
├── README.md
├── templates/
└── static/
```
