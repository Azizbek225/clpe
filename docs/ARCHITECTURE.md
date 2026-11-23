# Arxitektura

```
 Web (React)  ──┐                         ┌── Lab Agent (Celery worker, Docker/VBox/libvirt huquqi bilan)
 Desktop(Tauri)─┼── REST /api/v1, WS ── API (FastAPI) ── PostgreSQL
                │                         └── Redis (navbat)
                                               │
                             VirtualizationProvider interfeysi
                    ┌──────────────┬───────────┴──────┬──────────────┐
                 Docker        VirtualBox          libvirt/KVM       Mock
              (DVWA, Juice,   (Kali, Windows)     (Ubuntu, …)     (dev/test)
               Metasploitable)
                    └── har bir instansiya: alohida izolyatsiyalangan tarmoq(lar)
```

## Backend modullari

| Papka | Vazifa |
|---|---|
| `app/models/` | SQLAlchemy modellari: identity, learning, labs, ctf |
| `app/core/` | xavfsizlik (Argon2id, JWT, flag HMAC), RBAC ro'yxati, bog'liqliklar (ruxsat tekshiruvi, audit) |
| `app/api/v1/` | `auth`, `courses` (kurs/modul/dars CRUD), `assessment` (test, progress, sertifikat), `labs`, `vms`, `ctf`, `admin`, `ws` |
| `app/labengine/manifest.py` | YAML sxemasi, qisqa yozuvni normallashtirish, 9-bo'lim siyosati, sirlarni xeshlash, talaba uchun ko'rinish |
| `app/labengine/providers/` | adapterlar va reestr (`register_provider`) |
| `app/labengine/orchestrator.py` | IPAM, start oqimi + rollback, stop/cleanup, snapshot/restore, navbat, skan |
| `app/labengine/scanner.py` | nmap profil oq ro'yxati, nishon tekshiruvi, XML parser (defusedxml), topologiya quruvchi |
| `app/labengine/validators/` | baholash plaginlari (`register_validator`) |
| `app/services/` | kontent paketlari (import/eksport), progress/sertifikat, seed |

## Lab hayot sikli

`CREATED → PREPARING → STARTING → RUNNING → (RESETTING → RUNNING) → STOPPING → STOPPED`,
resurs yetmasa `QUEUED`, xatoda `ERROR` (yaratilgan resurslar teskari tartibda o'chiriladi).
Har bir o'tish `lab_events` va `audit_logs` ga yoziladi va WebSocket orqali UI'ga uzatiladi.
