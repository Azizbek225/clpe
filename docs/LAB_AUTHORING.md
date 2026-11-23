# Yangi laboratoriya qo'shish

Laboratoriya — bitta YAML fayl. Uni `backend/labs/` ga qo'ying (server ishga tushganda yuklanadi)
yoki **Admin → Laboratoriya muharriri** da yozib "Tekshirish" → "Saqlash" bosing. Kod o'zgarmaydi.

## To'liq misol

```yaml
id: web-cmdi-001                 # noyob, kichik harf/raqam/-
version: 1
title: {uz: "Command Injection", ru: "Инъекция команд", en: "Command Injection"}
description: {uz: "Ping formasidagi zaiflik orqali serverda buyruq bajaring."}
category: web-security
course: web-application-security # kurs slug'i (ixtiyoriy)
lab_type: offensive              # offensive | defensive | forensics | malware | general
difficulty: beginner             # beginner | intermediate | advanced
duration_minutes: 60             # tugagach avtomatik to'xtatiladi va tozalanadi
objectives:
  - {uz: "Kirish ma'lumotini tekshirmaslik xavfini tushunish"}
instructions:
  uz: |
    ## Vazifa
    `http://<dvwa-ip>/vulnerabilities/exec/` sahifasini o'rganing…

machines:
  - {name: attacker, template: kali-linux, role: attacker}           # brauzer terminali shu yerda
  - {name: web, template: dvwa, role: target, hidden: true}          # skan qilinmaguncha grafikda yo'q
networks:
  - {name: lab, type: isolated, internet: false}                     # bridged — taqiqlangan
topology: {reveal: discovered}   # full — barcha mashinalar boshidan ko'rinadi
resources: {cpu: 2, ram: 2048, max_machines: 4}

tasks:
  - id: port
    title: {uz: "Web port"}
    points: 10
    validation: {type: port_discovery, machine: web}       # kutilgan portlar shablondan yoki expected_ports
  - id: user
    title: {uz: "Web server qaysi foydalanuvchi nomidan ishlaydi?"}
    points: 40
    validation: {type: answer, answers: ["www-data"]}       # bir nechta to'g'ri javob mumkin
  - id: proof
    title: {uz: "Isbot fayli: /tmp/pwned"}
    points: 40
    validation: {type: vm_check, machine: web, check: file_exists, path: /tmp/pwned}
  - id: report
    title: {uz: "Tuzatish bo'yicha tavsiya"}
    points: 10
    validation: {type: manual}                              # o'qituvchi baholaydi

scoring: {maximum: 100, passing: 60, xp: 150}
cleanup: {snapshot_restore: true, auto_shutdown: true, destroy_on_stop: true}
```

Spetsifikatsiyadagi qisqa yozuv ham qabul qilinadi (`machines: [kali-linux, ubuntu-server]`,
`network: {type: isolated}`, `validation: port_discovery`).

## Tekshiruv turlari

| type | Talaba yuboradi | Sozlamalar |
|---|---|---|
| `flag` | matn | `flag` (saqlashda xeshlanadi) |
| `answer` | matn | `answers: [...]`, `case_sensitive` |
| `port_discovery` | portlar ro'yxati | `machine`, `expected_ports` (ixtiyoriy), `min_ratio` |
| `host_discovery` | IP'lar ro'yxati | `min_ratio` |
| `scan_coverage` | — (skan/import natijasi) | `machines`, `require_services` |
| `vm_check` | — | `machine`, `check: file_exists/file_absent`, `path` |
| `manual` | hisobot matni | — |

Yangi tur kerakmi? `register_validator("nomi")` bilan plagin yozing va `CLPE_PLUGIN_MODULES` ga qo'shing.

## Yangi nishon server (VM shablon)

`backend/catalog/machine_templates.yaml`:

```yaml
  wordpress-old:
    name: WordPress 4.x (zaif)
    operating_system: Debian
    image_reference: wordpress:4.9-php7.0     # Docker obraz yoki VM nomi / qcow2 yo'li
    image_checksum: sha256:…                   # production'da majburiy
    virtualization_provider: docker            # docker | virtualbox | libvirt
    role: target
    default_cpu: 0.5
    default_ram: 512
    meta:
      mock_ports: [{port: 80, service: http, product: Apache httpd, version: "2.4.25"}]
```
