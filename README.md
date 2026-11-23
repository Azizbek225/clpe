# CLPE — Cybersecurity Learning & Practice Environment

Kiberxavfsizlik bo'yicha ta'lim platformasi va virtual **cyber range**: nazariy kurslar, testlar,
izolyatsiyalangan tarmoqlardagi haqiqiy nishon serverlar (DVWA, Juice Shop, Metasploitable…),
tarmoqni skanerlash va **topologiya grafigi**, avtomatik baholash, CTF va administrator paneli.

Interfeys: **o'zbek** (asosiy), rus, ingliz. Platformalar: Web, Windows va Linux desktop (Tauri 2).

```
web/ ─ React + TypeScript + Tailwind (qorong'i kiber dizayn, i18n)      ┐
desktop/ ─ Tauri 2 qobig'i (web UI + sozlanadigan server manzili)        ├─ REST /api/v1 + WebSocket
backend/ ─ FastAPI + PostgreSQL + Redis/Celery                           ┘
   └─ app/labengine/ ─ Lab Engine: VirtualizationProvider (Docker · VirtualBox · libvirt · Mock),
                       YAML manifestlar, IPAM, skaner, topologiya, validator plaginlari
```

## Tez ishga tushirish

### A) Dev rejim (Docker shart emas — Mock provayder)

```bash
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload            # http://localhost:8000/docs  (Swagger)

cd ../web && npm install && npm run dev  # http://localhost:5173
```

Kirish: `admin` / `Admin12345!` (`.env` da o'zgartiring). Mock provayder laboratoriyalarni
simulyatsiya qiladi: start/stop/snapshot/reset, skan va graf to'liq ishlaydi.

### B) To'liq stek (haqiqiy nishon konteynerlar)

```bash
cp .env.example .env
docker build -t clpe/attacker:1.0 docker/images/attacker          # Kali + nmap, sqlmap, msf…
docker build -t clpe/ubuntu-target:1.0 docker/images/ubuntu-target
docker compose up -d --build                                      # http://localhost:8080
```

### C) Desktop (Windows / Linux)

```bash
cd desktop && npm install
npm run dev        # dev
npm run build      # .msi/.exe (Windows), .deb/.rpm/AppImage (Linux)
```
Linux uchun: `libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev`. Kirish oynasida server manzili kiritiladi.

## Asosiy imkoniyatlar

| Soha | Nima bor |
|---|---|
| **Auth** | Argon2id, qisqa muddatli JWT + refresh token rotatsiyasi (qayta ishlatish aniqlansa butun sessiya bekor), audit |
| **RBAC** | 8 rol (Super Admin, Org Admin, Instructor, Student, Lab Manager, Content Developer, Evaluator, Guest), 16 ruxsat |
| **Ta'lim** | 16 yo'nalish katalogi; 5 tasi kontentli (Fundamentals, Networking, Linux Security, Web Security, Ethical Hacking) — 47 dars, 69 test savoli, Markdown darslar, video, uz/ru/en tarjima, modul testlari, progress, avtomatik sertifikat + tekshirish kodi |
| **Laboratoriyalar** | 18 ta YAML lab: skanerlash, enumeration, ko'p hostli razvedka, pivoting; DVWA (SQLi, XSS, CMDi, upload, LFI, bruteforce); Juice Shop (razvedka, SQLi login); vsftpd, Samba, UnrealIRCd ekspluatatsiyasi; SSH bruteforce; Blue Team (web-shell, log tahlili) |
| **Lab Engine** | 8.2-bo'limdagi oqim (tarmoq → VM → snapshot → start → READY), xato bo'lsa to'liq rollback, navbat, kvota, muddat tugaganda avtomatik tozalash, snapshot/restore/reset |
| **Skan va graf** | Hujumchi mashina ichida nmap (oq ro'yxat profillar), yoki talabaning `nmap -oX` natijasini import; topologiya grafigi "discovered" rejimda faqat topilgan hostlarni ochadi |
| **Terminal** | Brauzerda xterm.js → WebSocket → lab konteyneri ichidagi shell (host'ga emas) |
| **Baholash** | Validator plaginlari: `flag`, `answer`, `port_discovery`, `host_discovery`, `scan_coverage`, `vm_check`, `manual` |
| **Gamification** | XP, level, global reyting, CTF (20 challenge, xeshlangan flaglar, leaderboard) |
| **Admin** | Dashboard, kurs/modul/dars/test muharriri (live preview, tarjimalar), YAML paket import/eksport, YAML lab muharriri + validator, foydalanuvchi/rol, Lab Engine va VM shablonlari, audit jurnali, talabalar laboratoriyalarini kuzatish |

## Kengaytirish (kodni o'zgartirmasdan)

- **Yangi laboratoriya** → `backend/labs/*.yaml` yoki Admin → *Laboratoriya muharriri*. Qo'llanma: [docs/LAB_AUTHORING.md](docs/LAB_AUTHORING.md)
- **Yangi VM / nishon server** → `backend/catalog/machine_templates.yaml` yoki `POST /api/v1/admin/machine-templates`
- **Yangi kurs / modul / dars / test** → Admin → *Kontent* (yoki YAML paket: `backend/content/courses/*.yaml`)
- **Yangi tekshiruv turi yoki virtualizatsiya provayderi** → plagin modul (`register_validator`, `register_provider`) + `CLPE_PLUGIN_MODULES`

## Xavfsizlik (9-bo'lim)

- Har bir talabaga alohida instansiya va alohida `/24` tarmoq (IPAM host'dagi band subnetlarni ham hisobga oladi)
- Docker tarmoqlari `internal=True` (internet yo'q), VirtualBox faqat `intnet`, libvirt `<forward>`siz
- `bridged` manifest darajasida rad etiladi; internetli lab faqat `CLPE_ALLOW_INTERNET_LABS=true` bo'lsa; malware lab — faqat to'liq izolyatsiya
- `privileged=False`, host'ga port chiqarilmaydi, volume yo'q, CPU/RAM/PID limitlari
- Provayderlar `shell=False` va tekshirilgan identifikatorlar bilan ishlaydi; skan nishoni lab CIDR ichida ekanligi tekshiriladi; nmap XML `defusedxml` bilan o'qiladi
- Flag va javoblar HMAC-SHA256 bilan xeshlanadi, talabaga yuborilmaydi
- Barcha status o'zgarishlari va harakatlar `audit_logs` ga yoziladi

## Testlar

```bash
cd backend && pytest -q                                   # 42 test (SQLite yoki CLPE_DATABASE_URL=postgres…)
CLPE_E2E_ATTACKER_IMAGE=instrumentisto/nmap:latest \
  python scripts/e2e_docker.py                            # haqiqiy Docker: tarmoq, skan, terminal, tozalash
cd ../web && npm run build                                 # TypeScript tekshiruvi + build
```

Holat va reja: [docs/ROADMAP.md](docs/ROADMAP.md) · Arxitektura: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
