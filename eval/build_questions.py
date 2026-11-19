"""Génère eval/questions.jsonl : 23 questions × 3 langues + 3 questions hors sujet × 3 langues = 78.

Chaque question a :
- gold  : les articles qui contiennent la réponse (vérifiés à la main dans les textes) ;
- facts : l'information attendue dans la réponse (un groupe = plusieurs écritures possibles) ;
- type  : factual, version (loi 2025-9), cross_doc (Code + Convention OIT), out_of_scope.

    python eval/build_questions.py
"""

import json
from pathlib import Path

BASE = [
    # id, type, gold, facts, fr, ar, en, réponse de référence (fr)
    ("q01", "factual", ["ct:113"], [["15", "خمسة عشر", "quinze", "fifteen"]],
     "Combien de jours de congé annuel payé un salarié peut-il avoir au maximum ?",
     "ما هي المدة القصوى للرخصة السنوية خالصة الأجر؟",
     "What is the maximum length of paid annual leave for a worker?",
     "Un jour par mois de travail, sans dépasser 15 jours dont 12 jours ouvrables."),
    ("q02", "factual", ["ct:79"], [["48", "ثمانية وأربعين", "ثمان وأربعين", "quarante-huit", "forty-eight"]],
     "Quelle est la durée maximale du travail par semaine ?",
     "ما هو الحد الأقصى لمدة العمل في الأسبوع؟",
     "What is the maximum number of working hours per week?",
     "48 heures de travail effectif par semaine."),
    ("q03", "factual", ["ct:95"], [["24", "أربع وعشرين", "أربعة وعشرين", "vingt-quatre", "twenty-four"]],
     "Combien d'heures de repos hebdomadaire un salarié doit-il avoir ?",
     "كم مدة الراحة الأسبوعية التي يجب منحها للعمال؟",
     "How long must the weekly rest period be?",
     "24 heures consécutives, le vendredi, le samedi ou le dimanche."),
    ("q04", "factual", ["ct:90"], [["75"]],
     "Comment sont payées les heures supplémentaires dans le régime de 48 heures par semaine ?",
     "ما هي نسبة الترفيع في أجر الساعات الإضافية في نظام 48 ساعة في الأسبوع؟",
     "What is the pay increase for overtime hours under the 48-hour weekly regime?",
     "Salaire horaire de base majoré de 75 %."),
    ("q05", "factual", ["ct:64"], [["30", "ثلاثين", "trente", "thirty"]],
     "Quelle est la durée du congé de maternité ?",
     "ما هي مدة عطلة الأمومة للمرأة العاملة؟",
     "How long is maternity leave?",
     "30 jours, prorogeables de 15 jours sur certificat médical."),
    ("q06", "factual", ["ct:376bis"], [["10", "عشرة", "dix", "ten"]],
     "Quel préavis faut-il donner avant une grève ?",
     "ما هو أجل التنبيه المسبق قبل الإضراب؟",
     "How much notice must be given before a strike?",
     "Un préavis de 10 jours."),
    ("q07", "factual", ["ct:14bis"], [["mois", "شهر", "month"]],
     "Quel est le préavis pour rompre un contrat à durée indéterminée ?",
     "ما هي مدة الإعلام المسبق لإنهاء عقد الشغل غير معين المدة؟",
     "What notice period is required to end an open-ended employment contract?",
     "Un mois, par lettre recommandée."),
    ("q08", "factual", ["ct:22"], [["jour", "يوم", "day"]],
     "À quelle indemnité de fin de service a droit un salarié licencié ?",
     "ما هي مكافأة نهاية الخدمة التي يستحقها العامل المطرود؟",
     "What end-of-service payment does a dismissed worker receive?",
     "Un jour de salaire par mois de service effectif, sauf faute grave."),
    ("q09", "factual", ["ct:66"], [["12", "اثنتي عشرة", "اثنتي عشر", "douze", "twelve"]],
     "Les mineurs de 14 à 18 ans peuvent-ils travailler la nuit ?",
     "هل يجوز تشغيل الأطفال بين 14 و18 سنة ليلا؟",
     "Can minors aged 14 to 18 work at night?",
     "Non : repos de nuit d'au moins 12 heures consécutives, de 22 h à 6 h."),
    ("q10", "cross_doc", ["ct:56", "c138:7"], [["13", "ثلاثة عشر", "ثلاث عشرة", "treize", "thirteen"]],
     "À partir de quel âge un enfant peut-il faire des travaux légers ?",
     "من أي سن يمكن تشغيل الأطفال في أعمال خفيفة؟",
     "From what age can children do light work?",
     "13 ans (Code, art. 56 ; Convention 138, art. 7 : 13 à 15 ans)."),
    ("q11", "cross_doc", ["ct:53", "c138:2"], [["16", "ستة عشر", "seize", "sixteen"]],
     "Quel est l'âge minimum pour travailler en Tunisie ?",
     "ما هي السن الدنيا للتشغيل في تونس؟",
     "What is the minimum age for employment in Tunisia?",
     "16 ans (Code, art. 53) ; la Convention 138 impose de fixer un âge minimum."),
    ("q12", "cross_doc", ["ct:58", "c138:3"], [["18", "ثمانية عشر", "ثماني عشرة", "dix-huit", "eighteen"]],
     "Quel est l'âge minimum pour un travail dangereux pour la santé ?",
     "ما هي السن الدنيا للأعمال الخطرة على الصحة؟",
     "What is the minimum age for work that is dangerous to health or safety?",
     "18 ans (Code, art. 58 ; Convention 138, art. 3)."),
    ("q13", "factual", ["ct:157"], [["40", "أربعين", "quarante", "forty"]],
     "À partir de combien de travailleurs une entreprise doit-elle créer une commission consultative ?",
     "ابتداء من كم عاملا يجب إحداث لجنة استشارية للمؤسسة؟",
     "From how many workers must a company set up a consultative committee?",
     "Au moins 40 travailleurs permanents."),
    ("q14", "factual", ["ct:153"], [["500"]],
     "Quand une entreprise doit-elle créer son propre service de médecine du travail ?",
     "متى يجب على المؤسسة إحداث مصلحة طب الشغل خاصة بها؟",
     "When must a company create its own occupational health service?",
     "À partir de 500 travailleurs."),
    ("q15", "factual", ["ct:5bis"], [],
     "La loi interdit-elle la discrimination entre hommes et femmes au travail ?",
     "هل يمنع القانون التمييز بين الرجل والمرأة في العمل؟",
     "Does the law forbid discrimination between men and women at work?",
     "Oui, aucune discrimination entre l'homme et la femme."),
    ("q16", "factual", ["ct:21"], [["inspection", "تفقدية", "inspector", "inspectorate"]],
     "Que doit faire un employeur avant un licenciement pour raisons économiques ?",
     "ماذا يجب على المؤجر قبل طرد العمال لأسباب اقتصادية؟",
     "What must an employer do before dismissing workers for economic reasons?",
     "Le notifier au préalable à l'inspection du travail."),
    ("q17", "version", ["ct:6-3"], [["6", "ستة", "six"]],
     "Quelle est la durée maximale de la période d'essai ?",
     "ما هي المدة القصوى لفترة التجربة؟",
     "What is the maximum length of the probation period?",
     "6 mois, renouvelable une seule fois (loi 2025-9)."),
    ("q18", "version", ["ct:6-4"], [["exception", "استثنائ", "exceptional"]],
     "Depuis la réforme de 2025, quand peut-on conclure un CDD ?",
     "متى يجوز إبرام عقد شغل لمدة معينة بعد تنقيح 2025؟",
     "Since the 2025 reform, when can a fixed-term contract be used?",
     "Seulement dans des cas exceptionnels (surcroît d'activité, remplacement, travaux saisonniers…)."),
    ("q19", "version", ["ct:28"], [["interdit", "تمنع", "يمنع", "ممنوع", "prohibit", "forbidden", "banned"]],
     "La sous-traitance de main-d'œuvre est-elle autorisée ?",
     "هل يجوز اللجوء إلى مناولة اليد العاملة؟",
     "Is labour-only subcontracting allowed?",
     "Non, elle est interdite (loi 2025-9)."),
    ("q20", "version", ["ct:29"], [["10000", "عشرة آلاف", "dix mille", "ten thousand"]],
     "Quelle amende risque une personne qui pratique la sous-traitance de main-d'œuvre ?",
     "ما هي الخطية المستوجبة على مرتكب جريمة مناولة اليد العاملة؟",
     "What fine applies to a person who commits the offence of labour subcontracting?",
     "10 000 dinars pour une personne physique."),
    ("q21", "version", ["ct:17"], [["indéterminée", "غير معين", "indefinite", "open-ended", "permanent"]],
     "Que devient un CDD si le salarié continue à travailler après la fin du contrat ?",
     "ماذا يحدث إذا واصل الأجير العمل بعد انقضاء مدة العقد معين المدة؟",
     "What happens if a worker keeps working after a fixed-term contract ends?",
     "Il devient un contrat à durée indéterminée."),
    ("q22", "factual", ["ct:183"], [["prud", "دوائر الشغل", "labour court", "labor court", "tribunal"]],
     "Quelle juridiction règle les conflits individuels du travail ?",
     "ما هي الهيئة التي تنظر في نزاعات الشغل الفردية؟",
     "Which court settles individual labour disputes?",
     "Les conseils de prud'hommes (دوائر الشغل)."),
    ("q23", "factual", ["ct:117"], [["juin", "جوان", "june"]],
     "Pendant quelle période de l'année le congé annuel est-il accordé ?",
     "في أي فترة من السنة تمنح الرخصة السنوية؟",
     "During which period of the year is annual leave normally granted?",
     "Du 1er juin au 31 octobre."),
]

OUT_OF_SCOPE = [
    ("u01", "Le télétravail est-il réglementé par le Code du travail ?",
     "هل تنظم مجلة الشغل العمل عن بعد؟", "Does the Labour Code regulate remote work?"),
    ("u02", "Un salarié a-t-il un droit à la déconnexion en dehors des heures de travail ?",
     "هل للعامل الحق في قطع الاتصال خارج أوقات العمل؟",
     "Do employees have a right to disconnect outside working hours?"),
    ("u03", "Quelles règles protègent les livreurs des plateformes numériques ?",
     "ما هي القواعد التي تحمي عمال التوصيل عبر المنصات الرقمية؟",
     "What rules protect delivery workers of digital platforms?"),
]


def main() -> None:
    rows = []
    for qid, qtype, gold, facts, fr, ar, en, ref in BASE:
        for lang, text in (("fr", fr), ("ar", ar), ("en", en)):
            rows.append({"id": f"{qid}-{lang}", "group": qid, "lang": lang, "type": qtype,
                         "question": text, "gold": gold, "facts": facts, "reference": ref})
    for qid, fr, ar, en in OUT_OF_SCOPE:
        for lang, text in (("fr", fr), ("ar", ar), ("en", en)):
            rows.append({"id": f"{qid}-{lang}", "group": qid, "lang": lang, "type": "out_of_scope",
                         "question": text, "gold": [], "facts": [], "reference": "Pas de réponse dans les textes."})
    out = Path(__file__).with_name("questions.jsonl")
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} questions → {out}")


if __name__ == "__main__":
    main()