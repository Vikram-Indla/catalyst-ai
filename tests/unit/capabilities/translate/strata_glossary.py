"""A proposed strategy-module glossary, English to Arabic, as a test fixture only.

The real glossary is data the backend holds and sends; this copy exists to prove the rule on a
whole vocabulary. Every Arabic target here is an unreviewed machine draft awaiting the linguistic
review, never a reviewed term. A term with a second plausible rendering carries it as
`alternative`: the fixture sends both, so the source is ambiguous and must be reported, never
silently resolved. Each term has one English sentence of the module's own kind, and the stand-in
rendering of that sentence carries the target.
"""

from typing import NamedTuple


class Term(NamedTuple):
    """One governed term: its source, its target, a second rendering if one is plausible."""

    source: str
    target: str
    alternative: str | None = None


TERMS = (
    Term("Framework", "إطار العمل", "الإطار المرجعي"),
    Term("Perspective", "المنظور"),
    Term("Cycle", "الدورة الاستراتيجية", "دورة التخطيط"),
    Term("Period", "الفترة", "فترة القياس"),
    Term("Theme", "المحور الاستراتيجي", "التوجه الاستراتيجي"),
    Term("Charter", "ميثاق المحور", "الميثاق"),
    Term("OKR", "الأهداف والنتائج الرئيسية (OKR)", "OKR"),
    Term("Objective", "الهدف"),
    Term("Key Result", "النتيجة الرئيسية"),
    Term("KPI", "مؤشر الأداء الرئيسي", "مؤشر أداء رئيسي"),
    Term("Strategic KPI", "مؤشر الأداء الاستراتيجي"),
    Term("Project KPI", "مؤشر أداء المشروع"),
    Term("Threshold scheme", "مخطط العتبات", "سلم الحدود"),
    Term("Threshold", "العتبة", "الحد"),
    Term("Band", "النطاق", "الفئة"),
    Term("Project Card", "بطاقة المشروع"),
    Term("Project Objective", "هدف المشروع"),
    Term("Direct Component", "المكوّن المباشر", "المساهمة المباشرة"),
    Term("Portfolio", "المحفظة"),
    Term("Milestone", "المعلم الرئيسي", "المرحلة"),
    Term("Dependency", "الاعتمادية", "التبعية"),
    Term("Risk", "المخاطرة", "الخطر"),
    Term("Blocker", "العائق"),
    Term("Strategy Map", "الخريطة الاستراتيجية"),
    Term("Command centre", "مركز القيادة", "لوحة القيادة"),
    Term("Scorecard", "بطاقة الأداء المتوازن"),
    Term("Baseline", "خط الأساس"),
    Term("Target", "القيمة المستهدفة", "المستهدف"),
    Term("Actual", "القيمة الفعلية"),
    Term("Weight", "الوزن"),
    Term("Observation", "القراءة", "الرصد"),
    Term("Evidence", "الشواهد", "الأدلة"),
    Term("Status", "الحالة"),
    Term("Delivery health", "سلامة التنفيذ", "صحة التنفيذ"),
    Term("Strategic health", "السلامة الاستراتيجية", "الصحة الاستراتيجية"),
    Term("Benefit realisation", "تحقيق المنافع", "تحقق الفوائد"),
    Term("On track", "على المسار", "ضمن المستهدف"),
    Term("At risk", "معرّض للخطر"),
    Term("Off track", "خارج المسار"),
    Term("Not measured", "لم يُقَس", "غير مُقاس"),
    Term("Draft", "مسودة"),
    Term("Pending approval", "بانتظار الاعتماد"),
    Term("Changes requested", "مطلوب تعديلات"),
    Term("Approved", "معتمد", "موافق عليه"),
    Term("Rejected", "مرفوض"),
    Term("Effective", "ساري", "نافذ"),
    Term("Superseded", "مستبدَل", "حلت محله نسخة أحدث"),
    Term("Retired", "مُنهى", "ملغى"),
    Term("Active", "نشط"),
    Term("Locked", "مقفل"),
    Term("Closed", "مغلق"),
    Term("Approval task", "مهمة الاعتماد"),
    Term("Approver", "المعتمِد", "صاحب صلاحية الاعتماد"),
    Term("Accountable owner", "المالك المسؤول"),
    Term("Legal hold", "التحفظ القانوني", "الحجز القانوني"),
    Term("Retention policy", "سياسة الاحتفاظ"),
    Term("Disposition", "الإتلاف", "التصرف في السجلات"),
    Term("Disposition proof", "إثبات الإتلاف"),
    Term("Audit history", "سجل التدقيق", "سجل المراجعة"),
    Term("Owner", "المالك"),
    Term("Admin", "المسؤول"),
    Term("Member", "العضو"),
    Term("SE SME", "خبير تنفيذ الاستراتيجية"),
    Term("VM SME", "خبير إدارة القيمة"),
    Term("BSC SME", "خبير بطاقة الأداء المتوازن"),
    Term("STRATA Admin", "مسؤول STRATA"),
    Term("STRATA Viewer", "مطلع STRATA"),
)

FLAGGED = tuple(term for term in TERMS if term.alternative)
SETTLED = tuple(term for term in TERMS if not term.alternative)


def glossary() -> list[dict[str, str]]:
    """Return the fixture as a request's glossary: each target, then each alternative."""
    entries = [{"source": term.source, "target": term.target} for term in TERMS]
    return entries + [
        {"source": term.source, "target": term.alternative} for term in TERMS if term.alternative
    ]


def sentence(term: Term) -> str:
    """Return one English sentence of the module's kind that names the term once."""
    return f"The board noted the {term.source} on the record today."


def rendering(term: Term, target: str | None = None) -> str:
    """Return the stand-in's Arabic for the term's sentence, carrying the given rendering."""
    return f"سجّل المجلس {target or term.target} في السجل اليوم."
