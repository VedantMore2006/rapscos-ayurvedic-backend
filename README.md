# Rapscos Ayurvedic — Standalone Backend API

High-performance, secure backend API for the Rapscos Ayurvedic e-commerce platform and administration system.

## 🚀 Key Technologies & Architecture
* **Framework**: FastAPI (Python 3.12+) with asynchronous handlers
* **Database**: SQLite with Write-Ahead Logging (WAL mode) for ACID reliability and high concurrency
* **Security & Auth**:
  * Argon2id password hashing
  * Constant-time auth response floor (minimum 700ms) to eliminate side-channel and timing attacks
  * JWT access tokens with 30-day expiration
  * SlowAPI rate limiting on sensitive routes (auth, login, signup)
* **Image Management**: Media uploads and gallery indexing with size limits and slugified paths
* **Deployment**: Docker Compose with Nginx reverse proxy, automatic SSL path, and Let's Encrypt support

---

## ⚡ 1-Command VPS Setup (Hostinger)

On your Ubuntu/Debian VPS server, run:

```bash
git clone git@github.com:VedantMore2006/rapscos-ayurvedic-backend.git backend
cd backend
sudo bash setup.sh
```

### What `setup.sh` does automatically:
1. Installs Docker CE and Docker Compose plugin if missing
2. Configures UFW firewall rules (ports 80, 443, 8777)
3. Auto-detects public IP and generates a cryptographically secure `.env` file with random `JWT_SECRET`
4. Initializes persistent directories (`data/`, `media/`)
5. Builds and launches the Docker stack (`rapscos_api` and `rapscos_nginx`)
6. Seeds the database with all 36 products, 6 categories, and the default admin user
7. Performs health check verification

---

## 🔄 1-Command Production Updates

Whenever you push new backend features or catalog changes to this repository, simply run:

```bash
sudo bash update.sh
```

### What `update.sh` does automatically:
1. **Force-pulls** the latest commits from `origin/main` (cleanly discarding outdated code while preserving your live database `data/rapscos.db`, uploaded media in `media/`, and `.env`)
2. Rebuilds and restarts the Docker containers seamlessly
3. Runs database seed/migration scripts
4. Verifies `/health` endpoint response

---

## 📂 Project Structure

```
backend/
├── setup.sh             # 1-command VPS deployment script
├── update.sh            # 1-command VPS update script
├── Dockerfile           # Production container build
├── docker-compose.yml   # Multi-container orchestration (FastAPI + Nginx)
├── nginx.conf           # Reverse proxy, caching, and SSL configuration
├── requirements.txt     # Python dependencies
├── .env.example         # Template environment variables
├── app/
│   ├── main.py          # FastAPI application entry & CORS middleware
│   ├── database.py      # SQLite connection & WAL pragma
│   ├── models.py        # SQLAlchemy models (User, Category, Product)
│   ├── schemas.py       # Pydantic validation schemas
│   ├── auth.py          # Argon2id hashing, timing safety, JWT
│   ├── limiter.py       # SlowAPI rate limiter
│   └── routes/          # API Route modules
│       ├── auth.py      # Login, signup, password change
│       ├── account.py   # Customer profile updates
│       ├── products.py  # Product CRUD & WhatsApp click tracker
│       ├── categories.py# Category CRUD & bestseller sorting
│       ├── content.py   # Content editor synchronization
│       └── images.py    # Media uploads and gallery
├── data/
│   ├── content.json     # Initial catalog data
│   ├── accounts.json    # Initial accounts
│   └── rapscos.db       # Persistent SQLite database (WAL)
├── media/               # Uploaded product imagery
└── scripts/
    ├── seed.py          # Database seeding
    ├── seed_admin.py    # Standalone admin user creation
    ├── verify_backend.py# Automated API test suite
    └── e2e_full_test.py # Comprehensive end-to-end testing
```

---

## 💻 Local Development

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Seed database
python scripts/seed.py

# 4. Start local development server
uvicorn app.main:app --reload --port 8777
```

---

## 🌐 Repository Ecosystem & Architecture

The project ecosystem is organized across three GitHub repositories/remotes:

| Repository | Owner | Remote Name | Primary Role & Deployment |
|---|---|---|---|
| [`VedantMore2006/rapscos-ayurvedic-backend`](https://github.com/VedantMore2006/rapscos-ayurvedic-backend) | **Vedant** | Standalone VPS | **Production Backend API**<br>• Host: VPS (`88.222.212.15`)<br>• Docker Container: `rapscos-ayurvedic` (port `8094` ➔ `8777`)<br>• Reverse Proxy: Nginx + Let's Encrypt SSL<br>• Live Domain: `https://api.rapscosbio.com` |
| [`VedantMore2006/rapscos-ayurvedic-frontend`](https://github.com/VedantMore2006/rapscos-ayurvedic-frontend) | **Vedant** | `origin` | **Production Frontend & Deployment Repo**<br>• Host: GoDaddy cPanel (`public_html`)<br>• CI/CD: Automated GitHub Action (`deploy.yml`) via FTP<br>• Target Branches: `main`, `backend`<br>• Live Domain: `https://www.rapscosbio.com`<br>• Live Admin Panel: `https://www.rapscosbio.com/admin` |
| [`Surajivarkar/rapscos-ayurvedic`](https://github.com/Surajivarkar/rapscos-ayurvedic) | **Suraj** | `upstream` | **Upstream Frontend Development Repo**<br>• Working Branch: `backend`<br>• Role: Source repository for frontend features & UI iterations |

### Multi-Remote Synchronization Workflow

To pull fresh UI updates from Suraj's repo and automatically deploy them live to GoDaddy:

```bash
# 1. Pull latest UI code from Suraj
git pull upstream backend

# 2. Test or build locally (optional)
npm run build

# 3. Push to your production repo (automatically triggers GoDaddy FTP deploy)
git push origin main
```

