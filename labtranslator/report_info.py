"""Explicit translations of report headings and known specimen descriptions."""
import re

LABELS = {'受付番号':'Accession No.', '報告日':'Report date', '検体':'Specimen',
          '依頼元':'Requested by', '検査施設':'Laboratory'}
VALUES = {'血液（架空）':'Blood (synthetic)', '血液(架空)':'Blood (synthetic)',
          '血液':'Blood', '血清':'Serum', '血漿':'Plasma', '尿':'Urine',
          'デモ用':'For demonstration', 'LabTranslator 検証用サンプル':'LabTranslator validation sample'}


def refresh_info(items):
    for item in items:
        value = item['value']
        if item.get('manual_translation'):
            translated = item.get('english_value','')
        elif item['label'] in ('受付番号','報告日'):
            translated = value
        elif not value:
            translated = ''
        else:
            translated = VALUES.get(value, value if not re.search(r'[\u3040-\u30ff\u3400-\u9fff]',value) else '')
        item['english_label'] = LABELS[item['label']]
        item['translation'] = translated if item.get('confirmed',False) else ''
        item['status'] = '確認済み' if item.get('confirmed') and (translated or not value) else '要確認'


def extract_info(text, page=1, ocr=False):
    result = []
    pattern = re.compile(r'('+'|'.join(LABELS)+r')[：:]\s*')
    for line in text.splitlines():
        if '検査項目' in line and '単位' in line:
            break
        matches = list(pattern.finditer(line))
        for i,match in enumerate(matches):
            value = line[match.end():matches[i+1].start() if i+1<len(matches) else len(line)].strip()
            result.append(dict(label=match.group(1),original_value=value,value=value,page=page,
                               confirmed=not ocr,manual_translation=False,english_value='',raw=line))
    refresh_info(result)
    return result
