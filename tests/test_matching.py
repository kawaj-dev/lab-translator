import pytest
from labtranslator.normalization import normalize
from labtranslator.terminology import translate


@pytest.mark.parametrize('source,expected',[
 ('ＴＰ（総タンパク）','TP(総タンパク)'),('Ａｌｂ（アルブミン）','Alb(アルブミン)'),
 ('Alb ( アルブミン )','Alb(アルブミン)'),('Ｔ－Ｂｉｌ（総ビリルビン）','T-Bil(総ビリルビン)')])
def test_normalization(source,expected):
    assert normalize(source)==expected


@pytest.mark.parametrize('source,expected',[
 ('TP','TP'),('ALB（アルブミン）','ALB(Albumin)'),('AST(GOT)','AST(GOT)'),
 ('総たんぱく質','Total Protein'),('血清アルブミン','Serum Albumin'),
 ('血清クレアチニン','Serum Creatinine'),('血中尿素窒素','Blood Urea Nitrogen'),
 ('総ビリルビン','Total Bilirubin'),('直接ビリルビン','Direct Bilirubin'),
 ('間接ビリルビン','Indirect Bilirubin'),('Na(ナトリウム)','Na(Sodium)')])
def test_translation(db,source,expected):
    assert translate(db,source)[:2]==(expected,'照合済み')


@pytest.mark.parametrize('source',['Alb(総ビリルビン)','AST(GPT)','ビリルビン','総ビリルピン','好中球割合','好中球絶対数','知らない略語','TP(未知語)'])
def test_no_guess(db,source):
    output,status,_=translate(db,source)
    assert output=='' and status in ('要確認','未登録')
