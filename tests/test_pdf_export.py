import io
import pytest
import pdfplumber
from pypdf import PdfReader
from labtranslator.export import export
from labtranslator.ingestion import read_excel
from labtranslator.terminology import translate
from pathlib import Path


@pytest.mark.parametrize('letter',list('ABC'))
def test_pdf_demo_data(db,letter):
    rows=read_excel(Path(__file__).resolve().parents[1]/'demo_data/LabTranslator_demo_ABC.xlsx','デモ'+letter)
    for r in rows:
        r['translation'],r['status'],r['message']=translate(db,r['name'])
    result=export(rows,'pdf')
    with pdfplumber.open(io.BytesIO(result)) as book:
        assert len(book.pages)==1
        table=book.pages[0].extract_table({'vertical_strategy':'text','horizontal_strategy':'text'})
        text=book.pages[0].extract_text()
        for r in rows:
            assert r['translation'] in text
            assert r['value'] in text and r['unit'] in text
        assert '25.0' in text and '×10⁴/μL' in text and '\ufffd' not in text
    reader=PdfReader(io.BytesIO(result))
    fonts=reader.pages[0]['/Resources']['/Font'].get_object()
    assert any('/FontFile2' in f.get_object().get('/FontDescriptor',{}).get_object()
               for f in fonts.values() if '/FontDescriptor' in f.get_object())


def test_pdf_blanks_exclusion_and_symbols():
    rows=[dict(translation='MUST NOT APPEAR',status='要確認',value='25.0',unit='×10⁴/μL'),
          dict(translation='',status='未登録',value='<0.01',unit='μmol/L'),
          dict(translation='Excluded',status='照合済み',value='99',unit='mg/dL',excluded=True),
          dict(translation='Protein & Test <A>',status='照合済み',value='±0.5',unit='10⁹/L')]
    text=''.join(p.extract_text() for p in PdfReader(io.BytesIO(export(rows,'pdf'))).pages)
    for expected in ['CAUTION: 2 unresolved','25.0','×10⁴/μL','<0.01','μmol/L','±0.5','10⁹/L','Protein & Test <A>']:
        assert expected in text
    assert 'MUST NOT APPEAR' not in text and 'Excluded' not in text


def test_long_name_and_pagination():
    rows=[dict(translation=f'Test {i}: '+('Long laboratory name with qualifiers '*12),
               status='照合済み',value=f'{i}.00',unit='×10⁴/μL') for i in range(1,61)]
    result=export(rows,'pdf')
    with pdfplumber.open(io.BytesIO(result)) as book:
        assert len(book.pages)>1
        text=''.join(p.extract_text() for p in book.pages)
        for i in range(1,61):
            assert f'Test {i}:' in text and f'{i}.00' in text
        for i,page in enumerate(book.pages,1):
            page_text=page.extract_text()
            assert 'Test' in page_text and 'Result' in page_text and 'Unit' in page_text
            assert f'Page {i}' in page_text
            assert all(c['x0']>=30 and c['x1']<=page.width-30 and c['top']>=25 and c['bottom']<=page.height-18 for c in page.chars)


def test_missing_glyph_is_rejected():
    with pytest.raises(ValueError,match='表示できない文字'):
        export([dict(translation='Test\U0010FFFF',status='照合済み',value='1',unit='g/dL')],'pdf')
