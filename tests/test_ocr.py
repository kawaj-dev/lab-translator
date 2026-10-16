import io
from pathlib import Path
import pytest
from PIL import Image
from labtranslator import ingestion
from labtranslator.ingestion import read_document

DEMO=Path(__file__).resolve().parents[1]/'demo_data'


def words():
    def w(t,x,y):
        return dict(text=t,x0=x,top=y,bottom=y+10)
    return [w('検査',100,10),w('項目',130,10),w('結果',300,10),w('単位',400,10),
            w('総蛋白',100,30),w('7.2',300,30),w('g/dL',400,30)]


@pytest.mark.parametrize('ext',['png','jpg','jpeg'])
def test_image_ocr_adapter(tmp_path,monkeypatch,ext):
    path=tmp_path/f'image.{ext}'
    Image.new('RGB',(600,100),'white').save(path)
    monkeypatch.setattr(ingestion,'ocr_words',lambda image:words())
    rows,raw,warnings=read_document(path)
    assert not warnings and len(rows)==1
    assert rows[0]['original_name']=='総蛋白' and not rows[0]['confirmed']
    assert rows[0]['value']=='7.2' and '総蛋白' in raw


def test_ocr_dependency_error(monkeypatch):
    def fail(image):
        raise ValueError('日本語OCRデータが必要')
    monkeypatch.setattr(ingestion,'ocr_words',fail)
    rows,raw,warnings=read_document(DEMO/'LabTranslator_Demo_A.png')
    assert not rows and not raw and '日本語OCR' in warnings[0]


def test_image_pdf_rendering_adapter(tmp_path,monkeypatch):
    from pypdf import PdfWriter
    writer=PdfWriter()
    writer.add_blank_page(width=600,height=100)
    path=tmp_path/'scanned.pdf'
    with path.open('wb') as stream:
        writer.write(stream)
    monkeypatch.setenv('PDFTOPPM_CMD','test-pdftoppm')
    def render(arguments,**kwargs):
        assert arguments[0]=='test-pdftoppm' and '-png' in arguments
        Image.new('RGB',(600,100),'white').save(arguments[-1]+'.png')
    monkeypatch.setattr(ingestion.subprocess,'run',render)
    monkeypatch.setattr(ingestion,'ocr_words',lambda image:words())
    rows,raw,warnings=read_document(path)
    assert not warnings and rows[0]['name']=='総蛋白'
    assert not rows[0]['confirmed'] and rows[0]['page']==1


@pytest.mark.parametrize('letter',list('ABC'))
@pytest.mark.parametrize('kind',['png','pdf-ocr'])
def test_real_ocr(letter,kind,db):
    # Skip only when the runtime dependencies are unavailable. Parser failures
    # with an available engine must fail the test and remain visible.
    import os,shutil,pytesseract
    if os.environ.get('TESSERACT_CMD'):
        pytesseract.pytesseract.tesseract_cmd=os.environ['TESSERACT_CMD']
    elif Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe').exists():
        pytesseract.pytesseract.tesseract_cmd=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    try:
        languages=pytesseract.get_languages()
    except (pytesseract.TesseractNotFoundError,pytesseract.TesseractError):
        pytest.skip('Tesseract未導入：OCR精度は未検証')
    if not {'jpn','eng'}.issubset(languages):
        pytest.skip('jpn/eng未導入：OCR精度は未検証')
    if kind=='pdf-ocr' and not (os.environ.get('PDFTOPPM_CMD') or shutil.which('pdftoppm')):
        pytest.skip('Poppler未導入：画像PDFは未検証')
    extension='pdf' if kind=='pdf-ocr' else 'png'
    rows,raw,warnings=read_document(DEMO/f'LabTranslator_Demo_{letter}.{extension}',force_ocr=kind=='pdf-ocr')
    from labtranslator.terminology import translate
    import openpyxl
    book=openpyxl.load_workbook(DEMO/'LabTranslator_demo_ABC.xlsx',read_only=True)
    expected=list(book['期待結果・検証'].values)[4:14]
    book.close()
    assert len(rows)==10, warnings
    for record,exp in zip(rows,expected):
        assert translate(db,record['name'])[0]==exp['ABC'.index(letter)+1]
        assert (record['value'],record['unit'])==(exp[4],exp[5])
        assert not record['confirmed']
