"""Generate a report from the same matched rows used by the preview."""
import io
import os
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, LongTable, TableStyle, Spacer
from .translation_review import output_translation


def report_font(text):
    candidates = [os.environ.get('PDF_FONT_PATH'), r'C:\Windows\Fonts\meiryo.ttc',
                  r'C:\Windows\Fonts\arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    path = next((p for p in candidates if p and Path(p).is_file()), None)
    if not path:
        raise ValueError('PDF_FONT_PATHに必要な文字を含むTrueTypeフォントを指定してください。')
    name = 'LabReport-' + __import__('hashlib').sha256(path.encode()).hexdigest()[:12]
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
    glyphs = pdfmetrics.getFont(name).face.charWidths
    missing = sorted({c for c in text if not c.isspace() and ord(c) not in glyphs})
    if missing:
        raise ValueError('PDFフォントに表示できない文字があります。PDF_FONT_PATHを確認してください: ' + ' '.join(missing))
    return name


def export_pdf(rows, metadata=None):
    metadata = metadata or []
    active = [(i+1,r) for i,r in enumerate(rows) if not r.get('excluded')]
    statuses = {'照合済み':'Matched', '未登録':'Unregistered', '要確認':'Needs review'}
    def status_label(record):
        label = statuses.get(record.get('status'),'Needs review')
        if record.get('manual_translation'):
            label += ' / Pending' if record.get('translation_pending',True) else ' / User reviewed'
        return label
    # Never derive a translation from the source name, including for review rows.
    records = [[str(i),output_translation(r),
                r.get('value',''),r.get('unit',''),r.get('reference',''),status_label(r)]
               for i,r in active]
    unresolved = sum(not record[1] for record in records)
    font = report_font(''.join(str(v) for record in records for v in record)+''.join(m['english_label']+m['translation'] for m in metadata))
    style = ParagraphStyle('cell',fontName=font,fontSize=8,leading=12,splitLongWords=True,wordWrap='CJK')
    title = ParagraphStyle('title',parent=style,fontSize=16,leading=22,textColor=colors.HexColor('#14263F'))
    notice = ParagraphStyle('notice',parent=style,textColor=colors.HexColor('#88531D'),spaceAfter=10)
    def paragraph(value):
        # Preserve supplied spaces and line breaks without interpreting markup.
        text = escape(str(value)).replace(' ','&#160;').replace('\n','<br/>')
        return Paragraph(text,style)
    table = LongTable([[paragraph(v) for v in record] for record in
                      [['No.','Test','Result','Unit','Reference range','Status'],*records]],
                      colWidths=[25,174,65,85,90,80],repeatRows=1,splitByRow=1,splitInRow=1)
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#EAF0F6')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F5F8FB')]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),8),
        ('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#D5DFE9'))]))
    story = [Paragraph('LABORATORY TEST REPORT',title),Paragraph('SYNTHETIC DATA / DEMO',style),Spacer(1,14)]
    for item in metadata:
        story.append(paragraph(item['english_label']+': '+item['translation']))
    if metadata:
        story.append(Spacer(1,12))
    if any(item['status']=='要確認' for item in metadata):
        story.append(Paragraph('CAUTION: Report information includes unresolved fields. Check the source document.',notice))
    if unresolved:
        story.append(Paragraph(f'CAUTION: {unresolved} unresolved item(s) included. '
                               'Unconfirmed translations are left blank. '
                               'Check the source document before use.',notice))
    if not records:
        story.append(Paragraph('No test items selected for export.',style))
    story.append(table)
    stream = io.BytesIO()
    def footer(canvas, document):
        canvas.setFont(font,8)
        canvas.setFillColor(colors.HexColor('#61768A'))
        canvas.drawString(36,23,'SYNTHETIC DATA / DEMO - Not for medical decisions')
        canvas.drawRightString(A4[0]-36,23,f'Page {document.page}')
    SimpleDocTemplate(stream,pagesize=A4,leftMargin=36,rightMargin=36,topMargin=32,bottomMargin=42,
                      title='Laboratory Test Report',author='LabTranslator').build(story,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()
