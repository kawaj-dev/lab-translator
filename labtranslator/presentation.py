"""Presentation counts only; matching and translations remain unchanged."""
def review_summary(job):
    active = [r for r in job['rows'] if not r.get('excluded')]
    critical = sum(r.get('status') == '要確認' and any(t in r.get('message', '') for t in
        ('意味が一致しない', '列の対応', '空欄', '数式')) for r in active)
    return dict(total=len(active), review=sum(r.get('status') in ('未登録', '要確認') or r.get('translation_pending',False) for r in active),
                manual_pending=[dict(index=i,name=r['name'],reason=r.get('translation_notice','英訳の確認が必要')) for i,r in enumerate(job['rows']) if not r.get('excluded') and r.get('translation_pending')],
                metadata_review=sum(m.get('status')=='要確認' for m in job.get('metadata',[])),
                critical=critical+len(job.get('warnings', [])), blank=sum(not r.get('translation') for r in active),
                excluded=len(job['rows'])-len(active))
