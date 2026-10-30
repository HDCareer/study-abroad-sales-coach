"""Publish a verified, immutable local bundle; incomplete staging is not delivery."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

SCHEMA = 'skill3-review-delivery/1.0'
PAYLOADS = ('report.html', 'results.json', 'run.json')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify(directory):
    root = Path(directory)
    require(root.is_dir() and not root.is_symlink(), '交付目录不存在或为链接')
    require({p.name for p in root.iterdir()} == set(PAYLOADS)|{'DELIVERY.json'}, '交付文件缺失或混入其他文件')
    for name in (*PAYLOADS, 'DELIVERY.json'):
        require((root/name).is_file() and not (root/name).is_symlink(), '交付文件必须为普通文件')
    manifest = json.loads((root/'DELIVERY.json').read_text(encoding='utf-8'))
    require(isinstance(manifest, dict), '完成清单必须为对象')
    require(manifest.get('schema_version') == SCHEMA and manifest.get('status') == 'complete', '缺少有效完成标记')
    aid = manifest.get('analysis_id')
    require(isinstance(aid, str) and re.fullmatch(r'[0-9a-f]{64}',aid), '分析编号格式不正确')
    require(isinstance(manifest.get('files'),dict) and set(manifest['files']) == set(PAYLOADS), '完成清单文件范围不正确')
    for name in PAYLOADS:
        raw = (root/name).read_bytes()
        require(manifest['files'][name] == {'sha256': sha(raw), 'bytes': len(raw)}, '交付摘要/长度不一致：'+name)
    result = json.loads((root/'results.json').read_text(encoding='utf-8'))
    trace = json.loads((root/'run.json').read_text(encoding='utf-8'))
    require(isinstance(result, dict) and isinstance(trace, dict), '结果与运行记录必须为对象')
    html = (root/'report.html').read_text(encoding='utf-8')
    require(result.get('schema_version') == 'skill3-management-results/1.0' and result.get('analysis_id') == aid, '结果版本或分析编号不一致')
    require(re.findall(r'<main\b[^>]*\bdata-analysis-id="([^"]+)"',html) == [aid], 'HTML分析编号不一致或重复')
    require(trace.get('schema_version') == 'skill3-run-provenance/1.0' and result.get('provenance') == trace, '运行记录与结果不一致')
    require(manifest.get('skill_version') == result.get('skill_version'), '交付版本不一致')
    return manifest


def _write(path, raw):
    with path.open('xb') as handle:
        handle.write(raw); handle.flush(); os.fsync(handle.fileno())


def publish(directory, html, result):
    """Atomic directory visibility on one local filesystem; no mutable latest alias."""
    require(not Path(directory).is_symlink(), '交付目标不能为链接')
    target = Path(directory).resolve()
    from render_chat_review import private_output
    private_output(target)
    require(result.get('provenance') is not None, '完整交付必须有运行记录')
    payload = {'report.html': html.encode('utf-8'),
               'results.json': json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8'),
               'run.json': json.dumps(result['provenance'],ensure_ascii=False,indent=2).encode('utf-8')}
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.parent/('.'+target.name+'.delivery.lock')
    token = uuid.uuid4().hex
    stage = None; acquired = False
    try:
        with lock.open('xb') as handle:
            acquired = True
            handle.write(token.encode('ascii')); handle.flush(); os.fsync(handle.fileno())
        if target.exists():
            manifest = verify(target)
            require(manifest['analysis_id'] == result['analysis_id'] and all(
                manifest['files'][name] == {'sha256':sha(raw),'bytes':len(raw)} for name,raw in payload.items()),
                '目标已有不同或损坏交付；请使用新的修订目录，不覆盖原版')
            return {'status':'reused','directory':str(target),'analysis_id':result['analysis_id']}
        stage = Path(tempfile.mkdtemp(prefix='.'+target.name+'.staging-',dir=target.parent))
        for name, raw in payload.items(): _write(stage/name, raw)
        manifest = {'schema_version': SCHEMA, 'status':'complete', 'analysis_id':result['analysis_id'],
                    'skill_version':result['skill_version'], 'created_at':datetime.now(timezone.utc).isoformat(),
                    'files':{name:{'sha256':sha(raw),'bytes':len(raw)} for name,raw in payload.items()}}
        _write(stage/'DELIVERY.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
        verify(stage)
        require(not target.exists(), '提交前目标已出现，请核查并发交付')
        os.rename(stage, target); stage = None
        return {'status':'complete','directory':str(target),'analysis_id':result['analysis_id']}
    finally:
        # Only remove files created by this attempt, never recurse over user paths.
        if stage is not None:
            for name in (*PAYLOADS, 'DELIVERY.json'):
                path = stage/name
                if path.is_file() and not path.is_symlink(): path.unlink()
            stage.rmdir()
        if acquired and lock.is_file() and lock.read_text(encoding='ascii') == token:
            lock.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description='独立核验留学辅导销售助手交付目录，校验不重新分析客户')
    parser.add_argument('directory', type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = verify(args.directory)
        print(json.dumps({'valid':True,'analysis_id':manifest['analysis_id'],'skill_version':manifest['skill_version']},ensure_ascii=False))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print('交付检查失败：'+str(exc), file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())
