"""RBAC: rollar va ruxsatlar. Yangi ruxsat qo'shish = shu ro'yxatga qator qo'shish."""

PERMISSIONS: dict[str, str] = {
    "system:manage": "Butun tizimni boshqarish",
    "org:manage": "Tashkilotni boshqarish",
    "users:manage": "Foydalanuvchilarni boshqarish",
    "content:read": "Kontentni ko'rish",
    "content:write": "Kurs, modul, dars yaratish va tahrirlash",
    "quiz:write": "Testlarni tahrirlash",
    "labs:use": "Laboratoriyalarni ishga tushirish",
    "labs:author": "Laboratoriya manifestlarini yaratish/tahrirlash",
    "labs:manage": "Barcha laboratoriya instansiyalari va VM'larni boshqarish",
    "labs:monitor": "Talabalar laboratoriyalarini kuzatish",
    "templates:manage": "VM shablonlari va hostlarni boshqarish",
    "grades:write": "Topshiriqlarni baholash",
    "reports:read": "Hisobotlarni ko'rish",
    "ctf:play": "CTF'da qatnashish",
    "ctf:manage": "CTF tadbirlarini boshqarish",
    "audit:read": "Audit jurnalini ko'rish",
}

ROLES: dict[str, tuple[str, list[str]]] = {
    "super_admin": ("Super Administrator", list(PERMISSIONS)),
    "org_admin": ("Organization Admin", [
        "org:manage", "users:manage", "content:read", "content:write", "quiz:write", "labs:use",
        "labs:monitor", "reports:read", "ctf:play", "ctf:manage", "audit:read",
    ]),
    "instructor": ("Instructor", [
        "content:read", "content:write", "quiz:write", "labs:use", "labs:author", "labs:monitor",
        "grades:write", "reports:read", "ctf:play", "ctf:manage",
    ]),
    "student": ("Student", ["content:read", "labs:use", "ctf:play"]),
    "lab_manager": ("Lab Manager", [
        "content:read", "labs:use", "labs:author", "labs:manage", "labs:monitor", "templates:manage",
    ]),
    "content_developer": ("Content Developer", [
        "content:read", "content:write", "quiz:write", "labs:use", "labs:author",
    ]),
    "evaluator": ("Evaluator", ["content:read", "grades:write", "reports:read", "labs:monitor"]),
    "guest": ("Guest", ["content:read"]),
}
