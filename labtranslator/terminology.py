import json
import re
from sqlalchemy import select
from .models import LabTerm, Alias, History
from .normalization import key, normalize


def snapshot(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def save_term(session, data, record_id=None, alias=False, actor='local-user', seed_key=None):
    model = Alias if alias else LabTerm
    name_field = 'alias_name' if alias else 'japanese_name'
    normalized_field = 'normalized_alias' if alias else 'normalized_name'
    name = data.get(name_field, '').strip()
    english = data.get('english_name', '').strip()
    if not name or len(name) > 200 or any(ord(c) < 32 for c in name):
        raise ValueError('名称は制御文字を含まない1～200文字で入力する。')
    if len(english) > 200 or (not alias and not english):
        raise ValueError('標準英語名を入力する（200文字以内）。')
    if '(' in normalize(name) or ')' in normalize(name):
        raise ValueError('複合表記は構成要素ごとに登録する。')
    for cls, field in [(LabTerm, LabTerm.normalized_name), (Alias, Alias.normalized_alias)]:
        found = session.scalar(select(cls).where(field == key(name)))
        if found and not (cls is model and found.id == record_id):
            raise ValueError('正規化後の名称が既存の標準名称・別名と重複または衝突する。')
    obj = session.get(model, record_id) if record_id else model()
    if obj is None:
        raise ValueError('対象が存在しない。')
    before = snapshot(obj) if record_id else {}
    if alias:
        term_id = int(data.get('term_id', 0))
        if not session.get(LabTerm, term_id):
            raise ValueError('対応する検査項目を選択する。')
        obj.term_id = term_id
    setattr(obj, name_field, name)
    setattr(obj, normalized_field, key(name))
    obj.english_name = english
    obj.specimen_type = data.get('specimen_type', '').strip()
    if seed_key:
        obj.seed_key = seed_key
    session.add(obj)
    session.flush()
    session.add(History(target_table=obj.__tablename__, target_id=obj.id,
                        action='update' if record_id else 'create',
                        before_data=json.dumps(before, ensure_ascii=False, default=str),
                        after_data=json.dumps(snapshot(obj), ensure_ascii=False, default=str), changed_by=actor))
    return obj


def lookup(session, text):
    term = session.scalar(select(LabTerm).where(LabTerm.normalized_name == key(text)))
    alias = session.scalar(select(Alias).where(Alias.normalized_alias == key(text)))
    if term and alias:
        return None
    if term:
        return term.id, term.english_name
    if alias:
        term = session.get(LabTerm, alias.term_id)
        return term.id, alias.english_name or term.english_name
    return None


def translate(session, text):
    output = normalize(text)
    parts = re.fullmatch(r'([^()]+)\(([^()]+)\)', output)
    if parts:
        left, right = parts.groups()
        a, b = lookup(session, left), lookup(session, right)
        if not a or not b or a[0] != b[0]:
            return '', '要確認', '複合表記の意味が一致しない、または未登録'
        def render(value, match):
            return match[1] if re.search(r'[\u3040-\u30ff\u3400-\u9fff]', value) else value
        return f'{render(left, a)}({render(right, b)})', '照合済み', ''
    match = lookup(session, output)
    if not match:
        return '', '未登録', '標準名称・別名に完全一致しない'
    return (match[1] if re.search(r'[\u3040-\u30ff\u3400-\u9fff]', output) else output), '照合済み', ''
