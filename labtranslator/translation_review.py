"""Document-local English overrides; never writes terminology tables."""
SOURCE_FIELDS = ('name','value','unit','reference')


def source_snapshot(record):
    return {field:record.get(field,'') for field in SOURCE_FIELDS}


def reset_manual(record):
    for field in ('manual_english','translation_basis','reconfirmation_reason'):
        record.pop(field,None)
    record.update(manual_translation=False,translation_confirmed=False,needs_reconfirmation=False)


def update_manual(record, form, previous_source):
    if form.get('action') == 'restore_translation':
        reset_manual(record)
        return
    if 'english' in form:
        english = form['english']
        if len(english)>1000 or any(ord(c)<32 and c not in '\n\r\t' for c in english):
            raise ValueError('英訳は制御文字を含まない1000文字以内で入力してください。')
        # An existing override remains an override until explicitly restored.
        if record.get('manual_translation') or english != record.get('master_translation',''):
            record['manual_translation'] = True
            record['manual_english'] = english
            record['translation_confirmed'] = 'translation_confirmed' in form and bool(english.strip())
            record['translation_basis'] = source_snapshot(record)
            if record['translation_confirmed']:
                record['needs_reconfirmation'] = False
                record.pop('reconfirmation_reason',None)
    if record.get('manual_translation') and source_snapshot(record) != previous_source:
        record['translation_confirmed'] = False
        record['needs_reconfirmation'] = True
        record['reconfirmation_reason'] = '検査項目名・検査値・単位・基準範囲が変更されたため、英訳の再確認が必要'


def apply_manual(record):
    """Called after ordinary matching, preserving its status and diagnostics."""
    if not record.get('manual_translation'):
        record['translation_pending'] = False
        record['translation_notice'] = ''
        return
    if record.get('translation_confirmed') and record.get('translation_basis') != source_snapshot(record):
        record['translation_confirmed'] = False
        record['needs_reconfirmation'] = True
        record['reconfirmation_reason'] = '原文側の内容が変更されたため、英訳の再確認が必要'
    source_ready = record.get('confirmed') and all(record.get(f,'').strip() for f in ('name','value','unit'))
    source_ready = source_ready and not any(record.get(f,'').startswith('=') for f in ('value','unit'))
    ready = bool(record.get('translation_confirmed') and record.get('manual_english','').strip() and source_ready)
    record['translation_pending'] = not ready
    record['translation'] = record.get('manual_english','') if ready and not record.get('excluded') else ''
    if record.get('needs_reconfirmation'):
        notice = record.get('reconfirmation_reason','英訳の再確認が必要')
    elif not record.get('translation_confirmed'):
        notice = '手動英訳が未確認のため空欄で出力されます。英訳を確認してください。'
    elif not source_ready:
        notice = '原資料との照合確認または検査項目名・検査値・単位の確認が必要なため空欄で出力されます。'
    else:
        notice = '手動英訳・利用者確認済み（この報告書のみ）'
    record['translation_notice'] = notice
    if not record.get('excluded'):
        record['message'] = ' / '.join(filter(None,[record.get('message',''),notice]))


def output_translation(record):
    if record.get('manual_translation'):
        return record.get('translation','') if not record.get('translation_pending',True) else ''
    return record.get('translation','') if record.get('status')=='照合済み' else ''
