import pytest
from sqlalchemy import select,func
from labtranslator.models import LabTerm,Alias,History
from labtranslator.terminology import save_term,translate
from labtranslator.seed import seed


def test_alias_and_history(db):
    term=db.scalar(select(LabTerm).where(LabTerm.japanese_name=='総蛋白'))
    before=db.scalar(select(func.count()).select_from(History))
    alias=save_term(db,{'alias_name':'検証用蛋白','term_id':term.id},alias=True)
    db.commit()
    assert translate(db,'検証用蛋白')[0]=='Total Protein'
    save_term(db,{'alias_name':'検証用蛋白改','term_id':term.id},record_id=alias.id,alias=True)
    db.commit()
    assert translate(db,'検証用蛋白改')[0]=='Total Protein'
    assert db.scalar(select(func.count()).select_from(History))==before+2
    history=db.scalar(select(History).order_by(History.id.desc()))
    assert '検証用蛋白' in history.before_data and '検証用蛋白改' in history.after_data


@pytest.mark.parametrize('name',['ＴＰ','総蛋白',' Alb ','','Alb(総ビリルビン)'])
def test_reject_collision(db,name):
    with pytest.raises(ValueError):
        save_term(db,{'alias_name':name,'term_id':1},alias=True)


def test_seed_preserves_edits(db):
    term=db.scalar(select(LabTerm).where(LabTerm.seed_key=='term-0'))
    save_term(db,{'japanese_name':'総蛋白変更','english_name':'Edited'},record_id=term.id)
    alias=db.scalar(select(Alias).where(Alias.seed_key=='alias-0-0'))
    save_term(db,{'alias_name':'変更済み別名','english_name':'Edited Alias','term_id':term.id},alias=True,record_id=alias.id)
    db.commit()
    before=db.scalar(select(func.count()).select_from(History))
    seed(db)
    db.commit()
    assert term.english_name=='Edited' and alias.english_name=='Edited Alias'
    assert db.scalar(select(func.count()).select_from(LabTerm))==13
    assert db.scalar(select(func.count()).select_from(History))==before
