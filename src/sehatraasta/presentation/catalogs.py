"""UI-only wording. Urdu/Pashto drafts require a named human reviewer.

Each tuple contains English, Urdu, Pashto. Review status is carried on EVERY
returned message, not inferred from the page language by its consumers.
"""
LANGUAGES = {"en": ("English", "ltr"), "ur": ("اردو", "rtl"), "ps": ("پښتو", "rtl")}

MESSAGES = {
    "warning.synthetic": ("Synthetic examples only. Not for medical care.", "صرف فرضی مثالیں۔ طبی نگہداشت کے لیے نہیں۔", "یوازې فرضي بېلګې. د طبي پاملرنې لپاره نه دي."),
    "warning.review": ("Translation review pending.", "ترجمے کا انسانی جائزہ باقی ہے۔", "د ژباړې انساني بیاکتنه پاتې ده."),
    "action.save": ("Save", "محفوظ کریں", "خوندي کړئ"),
    "action.create": ("Create a record", "نیا ریکارڈ بنائیں", "نوی ریکارډ جوړ کړئ"),
    "action.back": ("Back to list", "فہرست پر واپس جائیں", "لړلیک ته بېرته لاړ شئ"),
    "action.retry": ("Try again", "دوبارہ کوشش کریں", "بیا هڅه وکړئ"),
    "action.edit": ("Edit", "ترمیم کریں", "سمون ورکړئ"),
    "action.bundles": ("View bundles", "بنڈل دیکھیں", "بنډلونه وګورئ"),
    "action.bundle_new": ("New referral", "نیا ریفرل", "نوې راجع کول"),
    "action.cost_new": ("Add a cost", "خرچ شامل کریں", "لګښت زیات کړئ"),
    'action.upload': ('Add a file', 'فائل شامل کریں', 'فایل زیات کړئ'),
    "action.download": ("Download", "ڈاؤن لوڈ کریں", "ډاونلوډ کړئ"),
    "action.delete": ("Delete", "حذف کریں", "ړنګ کړئ"),
    "action.cancel": ("Cancel", "منسوخ کریں", "لغوه کړئ"),
    "action.print": ("Print view", "پرنٹ منظر", "د چاپ بڼه"),
    "action.export": ("Export JSON", "JSON برآمد کریں", "JSON صادر کړئ"),
    "action.backup": ("Create backup", "بیک اپ بنائیں", "شاتړ جوړ کړئ"),
    "action.check": ("Check without importing", "درآمد کیے بغیر جانچیں", "له واردولو پرته یې وګورئ"),
    "action.restore": ("Restore into a new folder", "نئے فولڈر میں بحال کریں", "په نوي پوښۍ کې بېرته جوړ کړئ"),
    "action.find": ("Find", "تلاش کریں", "ولټوئ"),
    "action.language": ("Change interface language", "انٹرفیس کی زبان بدلیں", "د مخ ژبه بدله کړئ"),
    "nav.skip": ("Skip to main content", "اصل مواد پر جائیں", "اصلي منځپانګې ته لاړ شئ"),
    "nav.language": ("Interface language", "انٹرفیس کی زبان", "د مخ ژبه"),
    "state.empty": ("No records yet.", "ابھی کوئی ریکارڈ نہیں۔", "تر اوسه ریکارډ نشته."),
    "state.preview": ("State preview: no record is saved here.", "حالت کا نمونہ: یہاں ریکارڈ محفوظ نہیں ہوتا۔", "د حالت بېلګه: دلته ریکارډ نه خوندي کېږي."),
    "state.not_reviewed": ("Not reviewed", "جائزہ نہیں لیا گیا", "بیاکتنه نه ده شوې"),
    "state.present": ("Present", "موجود", "شته"),
    "state.missing": ("Missing", "غائب", "نشته"),
    "state.pending": ("Pending", "زیرِ انتظار", "په تمه"),
    "state.not_applicable": ("Not applicable", "لاگو نہیں", "نه پلي کېږي"),
    "status.working": ("Working. Please wait.", "کام جاری ہے۔ انتظار کریں۔", "کار روان دی. انتظار وکړئ."),
    "status.saved": ("Record saved.", "ریکارڈ محفوظ ہو گیا۔", "ریکارډ خوندي شو."),
    "status.exported": ("Export created.", "برآمد شدہ فائل تیار ہے۔", "صادر شوی فایل جوړ شو."),
    "status.deleted": ("Record deleted.", "ریکارڈ حذف ہو گیا۔", "ریکارډ ړنګ شو."),
    "error.summary": ("Check the following fields.", "درج ذیل خانے درست کریں۔", "لاندې برخې سمې کړئ."),
    "error.required": ("Enter a value in this field.", "اس خانے میں معلومات درج کریں۔", "په دې برخه کې معلومات ولیکئ."),
    "error.invalid": ("Check the supplied value and its format.", "درج کردہ معلومات اور ان کی شکل درست کریں۔", "ورکړل شوي معلومات او بڼه یې وګورئ."),
    'error.name': ('Enter a name of 1 to 80 characters.', '۱ سے ۸۰ حروف کا نام درج کریں۔', 'له ۱ تر ۸۰ تورو نوم ولیکئ.'),
    'error.id': ('Enter a valid record ID.', 'درست ریکارڈ شناخت درج کریں۔', 'د ریکارډ سمه پېژند ولیکئ.'),
    "error.date": ("Enter a real date in YYYY-MM-DD format.", "درست تاریخ YYYY-MM-DD کی شکل میں درج کریں۔", "سمه نېټه د YYYY-MM-DD په بڼه ولیکئ."),
    "error.choice": ("Select one of the listed choices.", "فہرست میں سے ایک انتخاب کریں۔", "له لړلیک څخه یو انتخاب کړئ."),
    "error.amount": ("Enter a valid amount with at most two decimal places.", "زیادہ سے زیادہ دو اعشاری ہندسوں کے ساتھ درست رقم درج کریں۔", "سمه اندازه له اعشاریې وروسته تر دوو عددونو پورې ولیکئ."),
    'error.file': ('Select a PDF, PNG, or JPEG within 5 MiB.', '۵ MiB تک کی PDF، PNG یا JPEG فائل منتخب کریں۔', 'تر ۵ MiB پورې PDF، PNG یا JPEG فایل وټاکئ.'),
    "error.duplicate": ("This record already exists. No duplicate was saved.", "یہ ریکارڈ پہلے سے موجود ہے۔ نقل محفوظ نہیں کی گئی۔", "دا ریکارډ له مخکې شته. بل نقل خوندي نه شو."),
    "error.unavailable": ("Storage is unavailable. No save was confirmed. Try again later.", "ذخیرہ دستیاب نہیں۔ محفوظ ہونے کی تصدیق نہیں ہوئی۔ بعد میں کوشش کریں۔", "زېرمه نه شته. خوندي کېدل تایید نه شول. وروسته بیا هڅه وکړئ."),
    "error.not_found": ("The requested page or record was not found. Return to the list.", "مطلوبہ صفحہ یا ریکارڈ نہیں ملا۔ فہرست پر واپس جائیں۔", "غوښتل شوې پاڼه یا ریکارډ ونه موندل شو. لړلیک ته ستانه شئ."),
    "error.unexpected": ("Something went wrong. Return safely and try again.", "خرابی پیش آئی۔ واپس جائیں اور دوبارہ کوشش کریں۔", "ستونزه رامنځته شوه. بېرته لاړ شئ او بیا هڅه وکړئ."),
    "error.synthetic": ("Confirm that this is fictional practice data.", "تصدیق کریں کہ یہ فرضی مشقی معلومات ہیں۔", "تایید کړئ چې دا فرضي تمریني معلومات دي."),
    "field.id": ("Record ID", "ریکارڈ کی شناخت", "د ریکارډ پېژند"),
    "field.name": ("Display name", "ظاہری نام", "ښکاره نوم"),
    "field.birth_year": ("Birth year", "پیدائش کا سال", "د زېږېدو کال"),
    "field.language": ("Preferred language", "پسندیدہ زبان", "غوره ژبه"),
    "field.source": ("Source", "ماخذ", "سرچینه"),
    "field.destination": ("Destination", "منزل", "موخه"),
    "field.date": ("Date", "تاریخ", "نېټه"),
    "field.time": ("Time", "وقت", "وخت"),
    "field.category": ("Category", "زمرہ", "ډله"),
    "field.status": ("Status", "حالت", "حالت"),
    "field.amount": ("Amount in PKR", "رقم پاکستانی روپے میں", "اندازه په پاکستانیو روپیو"),
    "field.text": ("Original text", "اصل متن", "اصلي متن"),
    "field.note": ("Note", "نوٹ", "یادښت"),
    'field.file': ('File', 'فائل', 'فایل'),
    "field.reference": ("Source reference", "ماخذ کا حوالہ", "د سرچینې حواله"),
    "field.patient_id": ("Patient ID", "مریض کی شناخت", "د ناروغ پېژند"),
    "field.bundle_id": ("Bundle ID", "بنڈل کی شناخت", "د بنډل پېژند"),
    "field.created": ("Creation time", "بنانے کا وقت", "د جوړېدو وخت"),
    "field.facility": ("Facility", "ادارہ", "اداره"),
    "field.strength": ("Strength as supplied", "درج کردہ طاقت", "ورکړل شوی قوت"),
    "field.dose": ("Dose as supplied", "درج کردہ مقدار", "ورکړل شوې اندازه"),
    "field.route": ("Route as supplied", "درج کردہ طریقہ", "ورکړل شوې لاره"),
    "field.frequency": ("Frequency as supplied", "درج کردہ تکرار", "ورکړل شوی تکرار"),
    "field.duration": ("Duration as supplied", "درج کردہ مدت", "ورکړل شوې موده"),
    "field.instructions": ("Verbatim instructions", "ہدایات کا اصل متن", "د لارښوونو اصلي متن"),
    "field.interpretation": ("Verbatim result text", "نتیجے کا اصل متن", "د پایلې اصلي متن"),
    "field.modality": ("Imaging type as supplied", "درج کردہ امیجنگ کی قسم", "د انځور اخیستنې ورکړل شوی ډول"),
    "field.body_part": ("Body part as supplied", "درج کردہ جسمانی حصہ", "د بدن ورکړل شوې برخه"),
    "field.report": ("Verbatim report", "رپورٹ کا اصل متن", "د راپور اصلي متن"),
    "field.reviewer": ("Reviewer label", "جائزہ لینے والے کا نام", "د بیاکتونکي نوم"),
    "field.source_type": ("Source type", "ماخذ کی قسم", "د سرچینې ډول"),
    "field.link": ("Optional linked record", "اختیاری متعلقہ ریکارڈ", "اختیاري تړلی ریکارډ"),
    "field.archive": ("Backup archive", "بیک اپ فائل", "د شاتړ فایل"),
    "field.folder": ("New destination folder", "نیا منزل فولڈر", "نوې موخې پوښۍ"),
    "field.payload": ("QR payload or short ID", "QR کا متن یا مختصر شناخت", "د QR متن یا لنډ پېژند"),
    "state.draft": ("Draft", "مسودہ", "مسوده"),
    "state.ready_for_review": ("Ready for review", "جائزے کے لیے تیار", "د بیاکتنې لپاره چمتو"),
    "state.archived": ("Archived", "محفوظ شدہ", "زېرمه شوی"),
    "state.ordered": ("Ordered", "درخواست کی گئی", "غوښتل شوی"),
    "state.completed": ("Completed", "مکمل", "بشپړ شوی"),
    "state.cancelled": ("Cancelled", "منسوخ", "لغوه شوی"),
    "field.confirm": ("I confirm this is fictional practice data.", "میں تصدیق کرتا ہوں کہ یہ فرضی مشقی معلومات ہیں۔", "زه تاییدوم چې دا فرضي تمریني معلومات دي."),
    "help.source": ("Source not supplied", "ماخذ فراہم نہیں کیا گیا", "سرچینه نه ده ورکړل شوې"),
    'help.name': ('Enter the patient’s name.', 'مریض کا نام درج کریں۔', 'د ناروغ نوم ولیکئ.'),
    "help.date": ("Example: 2026-09-20", "مثال: 2026-09-20", "بېلګه: 2026-09-20"),
    "lab.title": ("School office appointment request", "اسکول دفتر سے ملاقات کی درخواست", "د ښوونځي دفتر د لیدنې غوښتنه"),
    "lab.list": ("Fictional appointment requests", "فرضی ملاقات کی درخواستیں", "د فرضي لیدنو غوښتنې"),
    "lab.warning": ("Learning lab only. No health data. Use fictional names.", "صرف مشقی تجربہ۔ صحت کی معلومات نہیں۔ فرضی نام استعمال کریں۔", "یوازې د زده کړې تمرین. روغتیايي معلومات مه کاروئ. فرضي نومونه وکاروئ."),
    "lab.states": ("State examples", "حالتوں کی مثالیں", "د حالتونو بېلګې"),
}

PAGE_TITLES = {
    "home": ("Home", "ابتدائی صفحہ", "کورپاڼه"),
    "patients": ("Patients", "مریض", "ناروغان"),
    "patient_new": ("Create patient", "مریض بنائیں", "ناروغ جوړ کړئ"),
    "patient": ("Patient", "مریض", "ناروغ"),
    "bundles": ("Referral bundles", "ریفرل بنڈل", "د راجع کولو بنډلونه"),
    "bundle_new": ("New referral", "نیا ریفرل", "نوې راجع کول"),
    "bundle": ("Bundle details", "بنڈل کی تفصیل", "د بنډل جزیات"),
    "bundle_edit": ("Edit bundle", "بنڈل میں ترمیم", "د بنډل سمون"),
    "medication": ("Medication record", "دوا کا ریکارڈ", "د درملو ریکارډ"),
    "order": ("Investigation order", "ٹیسٹ کی درخواست", "د ازموینې غوښتنه"),
    "result": ("Result record", "نتیجے کا ریکارڈ", "د پایلې ریکارډ"),
    "imaging": ("Imaging record", "امیجنگ کا ریکارڈ", "د انځور اخیستنې ریکارډ"),
    "instruction": ("Supplied instruction", "فراہم کردہ ہدایت", "ورکړل شوې لارښوونه"),
    "attachments": ("Attachments", "منسلک فائلیں", "نښلول شوي فایلونه"),
    "attachment_new": ("Add attachment", "فائل منسلک کریں", "فایل ونښلوئ"),
    "download": ("Download attachment", "منسلک فائل ڈاؤن لوڈ کریں", "نښلول شوی فایل ډاونلوډ کړئ"),
    "delete": ("Confirm deletion", "حذف کرنے کی تصدیق", "ړنګول تایید کړئ"),
    "costs": ("Reported costs", "بتائے گئے اخراجات", "راپور شوي لګښتونه"),
    "cost_new": ("Add reported cost", "بتایا گیا خرچ شامل کریں", "راپور شوی لګښت زیات کړئ"),
    "reviews": ("Category reviews", "زمروں کا جائزہ", "د ډلو بیاکتنې"),
    "audit": ("Activity history", "سرگرمی کی تاریخ", "د فعالیت مخینه"),
    "print": ("Printable summary", "قابلِ پرنٹ خلاصہ", "د چاپ وړ لنډیز"),
    "export": ("Export bundle", "بنڈل برآمد کریں", "بنډل صادر کړئ"),
    "lookup": ("Local lookup", "مقامی تلاش", "ځايي لټون"),
    'backup': ('Backup', 'بیک اپ', 'شاتړ'),
    "restore": ("Check and restore backup", "بیک اپ جانچیں اور بحال کریں", "شاتړ وګورئ او بېرته جوړ کړئ"),
}


def load_catalog(language):
    if language not in LANGUAGES:
        raise ValueError("unsupported interface language")
    position = list(LANGUAGES).index(language)
    rows = dict(MESSAGES)
    rows.update({"page." + key: value for key, value in PAGE_TITLES.items()})
    return {key: {"text": values[position],
                  "review_status": "reviewed" if language == "en" else "review_pending",
                  "reviewer": "technical English review" if language == "en" else None}
            for key, values in rows.items()}


def translate(key, language="en"):
    catalog = load_catalog(language)
    entry = catalog.get(key)
    if entry is None or not entry["text"].strip():
        return "[Missing translation: " + key + "]"
    return entry["text"]


def validate_catalogs():
    expected = set(load_catalog("en"))
    for language in LANGUAGES:
        catalog = load_catalog(language)
        if set(catalog) != expected:
            raise ValueError("translation keys do not match")
        for entry in catalog.values():
            if not entry["text"].strip() or entry["review_status"] not in ("reviewed", "review_pending"):
                raise ValueError("incomplete translation entry")
