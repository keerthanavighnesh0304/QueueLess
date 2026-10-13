# QueueLess — Hosted Aiven MySQL Database Initialization Guide

This guide explains how to safely perform a **one-time schema initialization and demo data seed** for your hosted Aiven MySQL database on Render.

---

## 1. Context: Why This Step is Required

In `app/main.py`, automatic table creation (`Base.metadata.create_all()`) is deliberately disabled on application startup to prevent concurrency race conditions, unexpected DDL locks, and startup delays in production environments.

When connecting to a newly provisioned Aiven MySQL database (`defaultdb`), the database initially contains no tables. Attempting to access endpoints like `GET /api/hospitals/` results in:
```
sqlalchemy.exc.ProgrammingError: (1146, "Table 'defaultdb.hospitals' doesn't exist")
```

The `init_hosted_db.py` script resolves this by safely and idempotently:
1. Creating all required tables defined in the SQLAlchemy models.
2. Provisioning the platform administrator account.
3. Seeding fictional `[Demo]` hospitals, departments, doctors, and user accounts.
4. Generating consultation sessions for **today and the next three calendar days** relative to the execution date.

---

## 2. Safety Guards Built into `init_hosted_db.py`

* **Localhost Blockade**: The script automatically detects and refuses to run if the resolved target host is `localhost`, `127.0.0.1`, `0.0.0.0`, `::1`, or `.local`. Your local MySQL development database cannot be touched by this script.
* **Mandatory Confirmation Flag**: Execution strictly requires the `--confirm-hosted` flag.
* **Isolated Engine**: Creates a dedicated, disposable SQLAlchemy engine connected only to the target hosted database. It never touches the local engine in `app.database`.
* **Idempotent by Design**: Never drops or truncates tables, deletes records, or overwrites existing user passwords or hospital data. Can be safely executed multiple times.
* **No Plaintext Passwords**: Uses salted `bcrypt` hashes for all user accounts.

---

## 3. Required Environment Variables

Configure these environment variables in your hosted environment (e.g., Render Dashboard → Service → Environment):

### Configuration Method A: Discrete Variables (Standard on Render)
* `DB_HOST`: Your Aiven MySQL service host (e.g. `mysql-project.aivencloud.com`)
* `DB_PORT`: Service port (e.g. `17890`)
* `DB_USER`: Username (e.g. `avnadmin`)
* `DB_PASSWORD`: Service password
* `DB_NAME`: Database name (e.g. `defaultdb`)
* `DB_SSL_MODE`: Set to `REQUIRED` (enables TLS/SSL encryption)
* `DB_SSL_CHECK_HOSTNAME`: `true`
* `ADMIN_INITIAL_PASSWORD`: Secure initial password for platform administrator
* `DEMO_ACCOUNTS_PASSWORD`: Secure initial password for demo staff and patient accounts
* `ADMIN_EMAIL`: (Optional) Platform admin email (default: `admin@queueless.local`)

### Configuration Method B: Explicit DATABASE_URL (Alternative)
* `DATABASE_URL`: Full connection URI (e.g. `mysql+pymysql://avnadmin:<PASSWORD>@<HOST>:<PORT>/defaultdb?ssl_ca=certs/aiven-ca.pem`)
* `ADMIN_INITIAL_PASSWORD`: Secure initial password for platform administrator
* `DEMO_ACCOUNTS_PASSWORD`: Secure initial password for demo staff and patient accounts

---

## 4. Exact Execution Commands

### Option A: From the Render Dashboard Shell (Recommended)
1. Go to your Render Dashboard → Select your **QueueLess Backend** service.
2. Click on the **Shell** tab in the service navigation.
3. Verify that your working directory is the backend root (contains `init_hosted_db.py`).
4. Execute:
   ```bash
   python init_hosted_db.py --confirm-hosted
   ```

### Option B: From Your Local Terminal (Targeting Aiven Directly)
If running from your machine against Aiven, provide the hosted variables in the shell session without saving them to `.env`:

#### PowerShell (Windows):
```powershell
cd C:\Projects\QueueLess\backend

$env:DB_HOST="<YOUR_AIVEN_HOST>"
$env:DB_PORT="<YOUR_AIVEN_PORT>"
$env:DB_USER="avnadmin"
$env:DB_PASSWORD="<YOUR_AIVEN_PASSWORD>"
$env:DB_NAME="defaultdb"
$env:DB_SSL_MODE="REQUIRED"
$env:ADMIN_INITIAL_PASSWORD="<STRONG_ADMIN_PASSWORD>"
$env:DEMO_ACCOUNTS_PASSWORD="<STRONG_DEMO_PASSWORD>"

venv\Scripts\python.exe init_hosted_db.py --confirm-hosted
```

#### Bash (Linux / macOS / WSL):
```bash
cd /path/to/QueueLess/backend

export DB_HOST="<YOUR_AIVEN_HOST>"
export DB_PORT="<YOUR_AIVEN_PORT>"
export DB_USER="avnadmin"
export DB_PASSWORD="<YOUR_AIVEN_PASSWORD>"
export DB_NAME="defaultdb"
export DB_SSL_MODE="REQUIRED"
export ADMIN_INITIAL_PASSWORD="<STRONG_ADMIN_PASSWORD>"
export DEMO_ACCOUNTS_PASSWORD="<STRONG_DEMO_PASSWORD>"

python init_hosted_db.py --confirm-hosted
```

---

## 5. Verification: How to Verify Tables and Future Sessions

Upon successful execution, the script prints a structured summary:
```
============================================================
DATABASE INITIALIZATION & VERIFICATION SUMMARY
============================================================
  • Total Tables in Schema:   6
  • Hospitals:                3
  • Departments:              3
  • Doctors:                  3
  • Consultation Sessions:    12
  • Users:                    4
  • Queue Tickets:            0
============================================================
[COMPLETE] Hosted database initialization completed successfully.
```

### Verification via Render API Endpoints
Once the script completes, test your live Render backend URL:
1. **Health Check**:
   ```
   GET https://<your-render-app>.onrender.com/api/health
   ```
   Expected response: `{"status": "healthy", "database_connected": true, ...}`
2. **Hospital Discovery**:
   ```
   GET https://<your-render-app>.onrender.com/api/hospitals
   ```
   Expected response: List of 2 approved demo hospitals (`City Care Hospital` and `Green Life Clinic`).
3. **Future Consultation Sessions**:
   ```
   GET https://<your-render-app>.onrender.com/api/hospitals/1/sessions
   ```
   Expected response: Active sessions covering today and the next three upcoming dates.

---

## 6. Security Reminders

* **Never commit secrets**: Do not commit Aiven passwords, JWT keys, or admin passwords to Git.
* **Keep `.env` private**: The `.env` file is ignored by Git; never add hosted credentials to your tracked files.
* **Clear terminal environment**: In local shells, clear sensitive variables after running by restarting the terminal or using:
  ```powershell
  Remove-Item Env:DB_PASSWORD, Env:ADMIN_INITIAL_PASSWORD, Env:DEMO_ACCOUNTS_PASSWORD
  ```
