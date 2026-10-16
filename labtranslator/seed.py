from sqlalchemy import select
from .models import LabTerm, Alias
from .terminology import save_term

TERMS = [
 ('総蛋白','Total Protein',['総蛋白質','総タンパク','総タンパク質','総たんぱく','総たんぱく質','TP']),
 ('アルブミン','Albumin',['Alb',('血清アルブミン','Serum Albumin','血清')]),
 ('AST','Aspartate Aminotransferase',['GOT']),
 ('ALT','Alanine Aminotransferase',['GPT']),
 ('尿素窒素','Blood Urea Nitrogen',['BUN',('血中尿素窒素','Blood Urea Nitrogen','血液')]),
 ('クレアチニン','Creatinine',['Cre',('血清クレアチニン','Serum Creatinine','血清')]),
 ('総ビリルビン','Total Bilirubin',['総ビリルビン値','T-Bil','T.Bil']),
 ('CRP','C-Reactive Protein',['C反応性蛋白','C反応性タンパク','C-反応性蛋白']),
 ('ヘモグロビン','Hemoglobin',['Hb','血色素量']),
 ('血小板数','Platelet Count',['PLT','血小板']),
 ('直接ビリルビン','Direct Bilirubin',['D-Bil']),
 ('間接ビリルビン','Indirect Bilirubin',['I-Bil']),
 ('ナトリウム','Sodium',['Na']),
]


def seed(session):
    for i, (jp, en, aliases) in enumerate(TERMS):
        token = f'term-{i}'
        term = session.scalar(select(LabTerm).where(LabTerm.seed_key == token))
        if not term:
            term = save_term(session, {'japanese_name':jp,'english_name':en}, actor='seed', seed_key=token)
        for j, entry in enumerate(aliases):
            token = f'alias-{i}-{j}'
            if session.scalar(select(Alias).where(Alias.seed_key == token)):
                continue
            name, english, specimen = entry if isinstance(entry, tuple) else (entry,'','')
            save_term(session, {'alias_name':name,'english_name':english,'specimen_type':specimen,'term_id':term.id}, alias=True, actor='seed', seed_key=token)
