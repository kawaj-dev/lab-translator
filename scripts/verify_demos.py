"""Print reproducible extraction metrics. Does not modify source workbooks."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from labtranslator.models import Base
from labtranslator.seed import seed
from labtranslator.ingestion import read_document
from labtranslator.terminology import translate


def main():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    book=openpyxl.load_workbook(ROOT/'demo_data/LabTranslator_demo_ABC.xlsx',read_only=True)
    expected=list(book['期待結果・検証'].values)[4:14]
    book.close()
    report=[]
    with Session(engine) as db:
        seed(db)
        for column,letter in enumerate('ABC',1):
            for extension,force in [('pdf',False),('pdf',True),('png',False)]:
                path=ROOT/'demo_data'/f'LabTranslator_Demo_{letter}.{extension}'
                result=read_document(path,force_ocr=force)
                rows,_,warnings=result
                details=[]
                translations=triples=0
                for i,exp in enumerate(expected):
                    record=rows[i] if i<len(rows) else None
                    translated=translate(db,record['name'])[0] if record else ''
                    name_ok=translated==exp[column]
                    full_ok=name_ok and (record['value'],record['unit'])==(exp[4],exp[5])
                    translations+=name_ok
                    triples+=full_ok
                    if not full_ok:
                        details.append(dict(no=i+1,expected=[exp[column],exp[4],exp[5]],
                                            actual=[translated,record['value'],record['unit']] if record else None))
                report.append(dict(demo=letter,mode='PDF強制OCR' if force else extension,
                                   extracted=len(rows),translation_matches=translations,all_field_matches=triples,
                                   total=10,warnings=warnings,mismatches=details,
                                   metadata=result.metadata,extraction=result.extraction,
                                   reference_ranges=[r.get('reference','') for r in rows]))
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':
    main()
