"""Local Flask application. Source files are immutable; job edits are separate JSON."""
import hmac
import io
import json
import os
import secrets
import uuid
import shutil
import subprocess
from pathlib import Path
import click
from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from werkzeug.exceptions import HTTPException
from .models import Base, LabTerm, Alias, History
from .seed import seed
from .terminology import save_term, translate
from .normalization import key
from .ingestion import read_excel, read_csv, read_document, row
from .export import export
from .presentation import review_summary
from .report_info import refresh_info
from .translation_review import source_snapshot, update_manual, apply_manual

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {'.pdf'}


def create_app(config=None):
    app = Flask(__name__, instance_path=str(ROOT/'instance'))
    app.config.from_mapping(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
                            DATA_DIR=ROOT/'instance', MAX_CONTENT_LENGTH=20*1024*1024,
                            SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_HTTPONLY=True)
    app.config.update(config or {})
    data_dir = Path(app.config['DATA_DIR'])
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(app.config.get('DATABASE_URL', 'sqlite:///'+str(data_dir/'labtranslator.db')))
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    app.extensions['db_engine'] = engine
    with Session(engine) as db, db.begin():
        seed(db)

    @app.before_request
    def csrf_check():
        session.setdefault('csrf', secrets.token_hex(24))
        if request.method == 'POST' and not hmac.compare_digest(session['csrf'], request.form.get('csrf','')):
            abort(400, 'フォームの有効期限が切れた。ページを再読込する。')

    @app.context_processor
    def template_context():
        return {'csrf':session.get('csrf',''),
                'pdf_preview_available':bool(os.environ.get('PDFTOPPM_CMD') or shutil.which('pdftoppm'))}

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        return response

    def job_path(job_id):
        try:
            if str(uuid.UUID(job_id)) != job_id:
                abort(404)
        except ValueError:
            abort(404)
        return data_dir/job_id

    def load_job(job_id):
        path = job_path(job_id)/'job.json'
        if not path.exists():
            abort(404)
        return json.loads(path.read_text(encoding='utf-8'))

    def save_job(job_id, job):
        target = job_path(job_id)/'job.json'
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(job, ensure_ascii=False), encoding='utf-8')
        temporary.replace(target)

    def match_job(job):
        refresh_info(job.get('metadata',[]))
        with Session(engine) as db:
            for r in job['rows']:
                translated, status, message = translate(db, r['name'])
                r.update(master_translation=translated,match_status=status,match_message=message)
                r['key'] = key(r['name'])
                if r['excluded']:
                    translated, status, message = '', '除外', '利用者が除外'
                elif not r['confirmed']:
                    translated, status, message = '', '要確認', r['reason'] or '原資料との確認が必要'
                elif not all(r[field].strip() for field in ('name','value','unit')):
                    translated, status, message = '', '要確認', '検査項目名・検査値・単位の空欄を確認'
                elif r['value'].startswith('=') or r['unit'].startswith('='):
                    translated, status, message = '', '要確認', '数式は処理対象外'
                r.update(translation=translated, status=status, message=message)
                apply_manual(r)

    @app.route('/', methods=['GET','POST'])
    def index():
        if request.method == 'GET':
            return render_template('upload.html')
        job_id = str(uuid.uuid4())
        folder = job_path(job_id)
        folder.mkdir()
        demo = request.form.get('demo','')
        if demo:
            if demo not in 'ABC' or len(demo) != 1:
                abort(400)
            ext = 'pdf'
            source = ROOT/'demo_data'/f'LabTranslator_Demo_{demo}.pdf'
            if not source.is_file():
                raise ValueError(f'デモ{demo}のPDF原本が存在しない。別形式への切り替えは行わない。')
            filename = source.name
            target = folder/('source.'+ext)
            target.write_bytes(source.read_bytes())
        else:
            upload = request.files.get('file')
            if not upload or not upload.filename:
                raise ValueError('ファイルを選択する。')
            filename = Path(upload.filename).name
            ext = Path(filename).suffix.lower().lstrip('.')
            if '.'+ext not in ALLOWED:
                raise ValueError('アップロード可能な形式：PDF（第1版）')
            target = folder/('source.'+ext)
            upload.save(target)
            from pypdf import PdfReader
            try:
                with target.open('rb') as stream:
                    if stream.read(5) != b'%PDF-':
                        raise ValueError('PDFではないファイルです。')
                    stream.seek(0)
                    pdf = PdfReader(stream)
                    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 20:
                        raise ValueError('暗号化されていない1～20ページのPDFを選択してください。')
            except Exception as exc:
                raise ValueError('有効なPDFを読み込めません。暗号化・破損・ページ数を確認してください。') from exc
        sheet = request.form.get('sheet') or ('デモ'+demo if demo else 'デモA')
        job = dict(filename=filename, extension=ext, rows=[], raw='', warnings=[])
        if ext == 'xlsx':
            import openpyxl
            book = openpyxl.load_workbook(target, read_only=True)
            job['sheets'] = [s for s in book.sheetnames if s != '期待結果・検証']
            book.close()
            if sheet not in job['sheets']:
                sheet = job['sheets'][0] if job['sheets'] else ''
            job['sheet'] = sheet
            job['rows'] = read_excel(target,sheet)
        elif ext == 'csv':
            job['rows'] = read_csv(target)
        else:
            result = read_document(target)
            job['rows'], job['raw'], job['warnings'] = result
            job['metadata'] = getattr(result,'metadata',[])
            job['extraction'] = getattr(result,'extraction',[])
        match_job(job)
        save_job(job_id,job)
        return redirect(url_for('results',job_id=job_id))

    @app.route('/jobs/<job_id>', methods=['GET','POST'])
    def results(job_id):
        job = load_job(job_id)
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'sheet' and job['extension'] != 'xlsx':
                raise ValueError('PDF原資料にはシート操作を使用できない。')
            if action == 'sheet' and job['extension'] == 'xlsx':
                job['sheet'] = request.form['sheet']
                job['rows'] = read_excel(job_path(job_id)/'source.xlsx',job['sheet'])
            elif action == 'ocr' and job['extension'] == 'pdf':
                if any(r.get('manual_translation') for r in job['rows']) and 'discard_manual' not in request.form:
                    raise ValueError('手動英訳があります。再抽出で失われることを確認してから実行してください。')
                result = read_document(job_path(job_id)/'source.pdf',force_ocr=True)
                job['rows'],job['raw'],job['warnings'] = result
                job['metadata'] = getattr(result,'metadata',[])
                job['extraction'] = getattr(result,'extraction',[])
            elif action == 'add':
                job['rows'].append(row(reason='手動追加行を原資料と確認'))
            elif action == 'recheck':
                pass
            else:
                for i,r in enumerate(job['rows']):
                    for field in ('name','value','unit'):
                        r[field] = request.form.get(f'{field}_{i}',r[field])
                        if len(r[field]) > 1000:
                            raise ValueError('各欄は1000文字以内。')
                    r['confirmed'] = f'confirmed_{i}' in request.form
                    r['excluded'] = f'excluded_{i}' in request.form
            match_job(job)
            save_job(job_id,job)
            if action == 'add':
                return redirect(url_for('edit_item',job_id=job_id,index=len(job['rows'])-1))
            return redirect(url_for('results',job_id=job_id))
        match_job(job)
        return render_template('results.html',job=job,job_id=job_id,summary=review_summary(job))

    @app.route('/jobs/<job_id>/items/<int:index>', methods=['GET','POST'])
    def edit_item(job_id,index):
        job = load_job(job_id)
        if index >= len(job['rows']):
            abort(404)
        record = job['rows'][index]
        match_job(job)
        if request.method == 'POST':
            previous_source = source_snapshot(record)
            for field in ('name','value','unit','reference'):
                value = request.form.get(field,record.get(field,''))
                if len(value) > 1000:
                    raise ValueError('各欄は1000文字以内。')
                record[field] = value
            record['confirmed'] = 'confirmed' in request.form
            record['excluded'] = 'excluded' in request.form
            update_manual(record,request.form,previous_source)
            match_job(job)
            save_job(job_id,job)
            flash('修正内容を保存して再照合した。')
            return redirect(url_for('results',job_id=job_id)+f'#item-{index}')
        match_job(job)
        return render_template('item.html',job=job,job_id=job_id,r=record,index=index)

    @app.route('/jobs/<job_id>/metadata/<int:index>',methods=['GET','POST'])
    def edit_metadata(job_id,index):
        job = load_job(job_id)
        if index >= len(job.get('metadata',[])):
            abort(404)
        record = job['metadata'][index]
        if request.method == 'POST':
            for field in ('value','english_value'):
                value = request.form.get(field,record.get(field,''))
                if len(value)>1000:
                    raise ValueError('各欄は1000文字以内。')
                record[field] = value
            record['manual_translation'] = 'manual_translation' in request.form
            record['confirmed'] = 'confirmed' in request.form
            match_job(job)
            save_job(job_id,job)
            flash('上部情報の修正・確認を保存した。')
            return redirect(url_for('results',job_id=job_id))
        match_job(job)
        return render_template('metadata.html',job_id=job_id,r=record)

    @app.get('/jobs/<job_id>/output')
    def output(job_id):
        job = load_job(job_id)
        match_job(job)
        return render_template('output.html',job=job,job_id=job_id,summary=review_summary(job))

    @app.get('/jobs/<job_id>/source')
    def source(job_id):
        job = load_job(job_id)
        return send_file(job_path(job_id)/('source.'+job['extension']))

    @app.get('/jobs/<job_id>/source-page/<int:page>')
    def source_page(job_id,page):
        job = load_job(job_id)
        if job['extension'] != 'pdf' or not 1 <= page <= 20:
            abort(404)
        from pypdf import PdfReader
        source = job_path(job_id)/'source.pdf'
        with source.open('rb') as stream:
            if page > len(PdfReader(stream).pages):
                abort(404)
        target = job_path(job_id)/f'preview-{page}.png'
        if not target.exists():
            exe = os.environ.get('PDFTOPPM_CMD') or shutil.which('pdftoppm')
            if not exe:
                raise ValueError('PDF画像プレビューにはPopplerが必要。原ファイルを開いて確認してください。')
            result = subprocess.run([exe,'-f',str(page),'-l',str(page),'-singlefile','-scale-to','1600',
                                     '-png',str(source)],capture_output=True,check=True,timeout=90)
            if not result.stdout.startswith(b'\x89PNG'):
                raise ValueError('PDF画像プレビューを生成できない。原ファイルを開いて確認してください。')
            target.write_bytes(result.stdout)
        return send_file(target,mimetype='image/png')

    @app.get('/jobs/<job_id>/export/<extension>')
    def download(job_id,extension):
        if extension not in ('xlsx','csv','pdf'):
            abort(404)
        job = load_job(job_id)
        match_job(job)
        return send_file(io.BytesIO(export(job['rows'],extension,job.get('metadata',[]))),as_attachment=True,
                         download_name='LabTranslator_result.'+extension,
                         mimetype={'csv':'text/csv; charset=utf-8','pdf':'application/pdf',
                                   'xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}[extension])

    @app.route('/terms',methods=['GET','POST'])
    def terms():
        with Session(engine) as db:
            if request.method == 'POST':
                with db.begin():
                    save_term(db,request.form,record_id=int(request.form['id']) if request.form.get('id') else None,
                              alias=request.form.get('kind')=='alias')
                flash('保存した。結果画面で再照合できる。')
                return redirect(url_for('terms'))
            return render_template('terms.html',terms=db.scalars(select(LabTerm).order_by(LabTerm.id)).all(),
                                   aliases=db.scalars(select(Alias).order_by(Alias.id)).all(),prefill=request.args.get('name',''))

    @app.get('/history')
    def history():
        with Session(engine) as db:
            return render_template('history.html',records=db.scalars(select(History).order_by(History.id.desc())).all())

    @app.get('/logo.svg')
    def logo():
        return send_file(ROOT/'docs/images/labtranslator-logo.svg',mimetype='image/svg+xml')

    @app.errorhandler(ValueError)
    def invalid(exc):
        return render_template('error.html',message=str(exc)),400

    @app.errorhandler(Exception)
    def unexpected(exc):
        if isinstance(exc,HTTPException):
            return render_template('error.html',message=exc.description),exc.code
        app.logger.exception('処理失敗')
        return render_template('error.html',message='ファイルを処理できない。形式・破損・依存関係を確認する。'),400

    @app.cli.command('init-db')
    def init_db():
        with Session(engine) as db, db.begin():
            seed(db)
        click.echo('初期データを確認した（既存の修正は保持）。')
    return app
