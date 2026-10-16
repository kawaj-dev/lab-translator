from labtranslator.report_info import extract_info,refresh_info
from labtranslator.ingestion import parse_words,read_document
from labtranslator.terminology import translate
from labtranslator.export import export
from pathlib import Path
import pytest
import io
import openpyxl
from pypdf import PdfReader


@pytest.mark.parametrize('letter',list('ABC'))
def test_pdf_metadata_and_exports(db,letter):
    result=read_document(Path('demo_data')/f'LabTranslator_Demo_{letter}.pdf')
    rows,_,warnings=result
    assert not warnings and len(rows)==10
    info={m['label']:m for m in result.metadata}
    assert len(info)==5
    assert info['報告日']['translation']=='2026/10/16'
    assert info['受付番号']['translation']==f'DEMO-{letter}-0001'
    assert info['検体']['original_value']=='血液（架空）'
    assert info['検体']['translation']=='Blood (synthetic)'
    assert result.extraction==[dict(page=1,method='text',status='success',message='')]
    for r in rows:
        assert r['reference_present'] and r['reference']==r['original_reference']==''
        r['translation'],r['status'],r['message']=translate(db,r['name'])
    pdf=PdfReader(io.BytesIO(export(rows,'pdf',result.metadata)))
    text=''.join(p.extract_text() for p in pdf.pages)
    for value in ['Report date','2026/10/16',f'DEMO-{letter}-0001','Blood (synthetic)','Reference range']:
        assert value in text
    for r in rows:
        assert r['translation'] in text and r['value'] in text and r['unit'] in text
    book=openpyxl.load_workbook(io.BytesIO(export(rows,'xlsx',result.metadata)))
    assert len(list(book['翻訳結果'].values))==11
    assert all(book['翻訳結果'].cell(i,10).value in (None,'') for i in range(2,12))
    assert len(list(book['報告書情報'].values))==6


def test_metadata_no_invention_unknown_and_ocr():
    info=extract_info('報告日：2020/01/02\n検体：未知検体\n受付番号：\n')
    assert [m['label'] for m in info]==['報告日','検体','受付番号']
    assert info[0]['translation']=='2020/01/02'
    assert info[1]['translation']=='' and info[1]['status']=='要確認'
    assert info[2]['value']==info[2]['translation']==''
    ocr=extract_info('検体：血清',ocr=True)
    assert not ocr[0]['confirmed'] and ocr[0]['translation']==''
    ocr[0].update(confirmed=True)
    refresh_info(ocr)
    assert ocr[0]['translation']=='Serum'


def test_reference_ranges_and_empty_fields():
    def w(text,x,y):
        return dict(text=text,x0=x,top=y,bottom=y+10)
    words=[w('検査項目',100,0),w('結果',200,0),w('単位',300,0),w('基準範囲',400,0),w('判定',500,0),
           w('総蛋白',100,20),w('7.2',200,20),w('g/dL',300,20),w('6.5～8.0',400,20),w('正常',500,20),
           w('AST',100,40),w('24',200,40),w('U/L',300,40)]
    rows=parse_words(words)
    assert rows[0]['reference']==rows[0]['original_reference']=='6.5～8.0'
    assert rows[1]['reference']==''
    assert rows[0]['unit']=='g/dL' and rows[0]['value']=='7.2'
    rows[0].update(translation='Total Protein',status='照合済み')
    text=''.join(p.extract_text() for p in PdfReader(io.BytesIO(export(rows[:1],'pdf'))).pages)
    assert '6.5～8.0' in text


def test_fragmented_reference_not_silently_confirmed():
    def w(text,x,y,x1=None):
        return dict(text=text,x0=x,x1=x1 if x1 is not None else x+15,top=y,bottom=y+10)
    words=[w('検査項目',100,0),w('結果',200,0),w('単位',300,0),w('基準範囲',400,0),
           w('総蛋白',100,20),w('7.2',200,20),w('g/dL',300,20),
           w('6.5',400,20,415),w('～',420,20,425),w('8.0',430,20,445)]
    result=parse_words(words)
    assert result[0]['reference']=='6.5 ～ 8.0'
    assert not result[0]['confirmed'] and '基準範囲' in result[0]['reason']
