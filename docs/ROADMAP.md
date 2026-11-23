# Holat: nima qurildi va nima rejada

Spetsifikatsiya juda katta (≈ 44 hafta). Ushbu birinchi o'tish — **ishlaydigan yadro**: barcha
qatlamlar ulangan, kengaytirish nuqtalari tayyor, qolgan ishlar shu yadro ustiga qo'shiladi.

## ✅ Qurildi va sinovdan o'tdi

- FastAPI backend, PostgreSQL/SQLite, OpenAPI (`/docs`), 6-bo'limdagi asosiy jadvallar (UUID, timestamps, soft delete, `organization_id`)
- Auth: Argon2id, JWT + refresh rotatsiya va qayta ishlatishni aniqlash; RBAC 8 rol
- Kurs → Modul → Dars → Tarjima; testlar, progress, XP/level, avtomatik sertifikat va tekshirish
- Lab Engine: `VirtualizationProvider` interfeysi; **Docker** adapteri (haqiqiy Docker'da e2e sinovdan o'tgan), **Mock** adapteri;
  8.2 oqimi + rollback, IPAM, kvota, navbat, muddat bo'yicha tozalash, snapshot/restore/reset, metrikalar
- YAML manifest + xavfsizlik siyosati (bridged/internet/malware), 6 ta tayyor lab, admin YAML muharriri
- Skaner (nmap hujumchi ichida), XML import, topologiya grafigi; WebSocket: lab holati va brauzer terminali
- CTF (hodisa, challenge, xeshlangan flag, leaderboard), reyting
- Web UI (uz/ru/en), admin panel (kontent, lab, foydalanuvchi, engine, audit), o'qituvchi uchun kuzatuv
- Tauri 2 desktop qobig'i (Linux'da release build tekshirildi), GitHub Actions (testlar, e2e, desktop installerlar)

## 🟡 Qisman (kod bor, real muhitda sinalmagan)

- **VirtualBox** adapteri (VBoxManage, linked clone, intnet, snapshot) — Windows host'da sinov kerak; VM ichida tekshiruv (`guestcontrol`) yo'q
- **libvirt/KVM** adapteri (izolyatsiyalangan tarmoq XML, qcow2 backing, snapshot) — KVM host'da sinov kerak
- Celery worker (Lab Agent) — compose'da sozlangan; asosiy testlar fon oqimi rejimida
- Multi-tenant: `organization_id` bo'yicha ajratish API'da; PostgreSQL **RLS** siyosatlari hali yo'q

## ⏭ Keyingi bosqichlar (rejada)

1. Alembic migratsiyalari va RLS siyosatlari
2. Kontent hajmi: 40 dars, 30 lab, 300 savol, 20 CTF challenge (MVP talabi) — hozir 15 dars, 6 lab, 15 savol, 5 challenge
3. VM konsoli (noVNC) Windows/Kali VM'lar uchun; VirtualBox/KVM real sinovlari; Windows 11 / Windows Server AD lablar
4. Desktop **offline** rejim: dars/testlarni lokal keshlash, lokal Docker lablar, keyinchalik sinxronlash va konfliktlarni hal qilish
5. Universitet Edition: fakultet/kafedra/guruhlar, guruhga topshiriq berish, rejalashtirish, guruhlararo CTF, hisobotlar (PDF/Excel)
6. MFA (TOTP) administratorlar uchun, parol tiklash emaili, rate limiting
7. Prometheus metrikalari + Grafana dashboard, markazlashgan loglar
8. Dinamik (har instansiyaga alohida) flaglar, Ansible orqali VM konfiguratsiyasi
9. Playwright UI testlari; Windows desktop installer sinovi
10. AI tutor / AI Lab Assistant (19-bo'lim)
