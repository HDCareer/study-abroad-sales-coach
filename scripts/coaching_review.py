"""Two-layer evidence checks and coaching views, never automatic staff judgments."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATES = {'gap': '可见缺口', 'sound': '未见明显缺口', 'unknown': '证据不足', 'not_applicable': '本案不适用'}
LAYERS = {'judgment': '第一层 · 销售判断', 'expression': '第二层 · 话术组织', 'execution': '执行兑现'}
PRIMARY = {'judgment': '主要是判断', 'expression': '主要是表达', 'both': '两层均有缺口', 'execution': '主要是执行', 'none': '未见明确缺口', 'unknown': '证据不足'}
APPLICATION = {'not_used': '未体现适用方法', 'partial': '只体现了部分', 'misapplied': '时机或条件不适用', 'appropriate': '已恰当体现', 'unknown': '不足以判断使用情况', 'not_applicable': '本案不适用'}
TRAINING = {'judgment': '练判断', 'expression': '练表达', 'combined': '先练判断，再练表达', 'execution': '落实执行', 'none': '保持并观察', 'verify': '先核证据'}


def canonical(text):
    return re.sub(r'\s+', '', re.sub(r'(?m)^\s*>\s?', '', text))


def source_text(path, api):
    api.require(isinstance(path, str) and '\\' not in path, 'library.path', '只允许相对Skill的正斜杠MD路径')
    target = (ROOT / path).resolve()
    api.require(target.is_relative_to(ROOT) and target.suffix == '.md' and
                (path == 'SKILL.md' or path.startswith('references/')), 'library.path', '来源须在Skill入口或references内')
    api.require(target.is_file(), 'library.path', '来源文件不存在')
    return target.read_text(encoding='utf-8-sig')


def validate(data, api):
    cfg = data['management']['coaching']
    api.require(cfg.get('version') == '1.0', 'coaching.version', '只支持1.0')
    api.choice(cfg.get('basis'), ('baseline', 'corrected_baseline'), 'coaching.basis')
    api.choice(cfg.get('previous_batch_status'), ('none', 'superseded'), 'coaching.previous_batch_status')
    if cfg['basis'] == 'corrected_baseline':
        api.require(cfg['previous_batch_status'] == 'superseded', 'coaching', '校正基线必须排除已被替代批次')
    api.string(cfg.get('assessment'), 'coaching.assessment')
    cases = {c['id']: c for c in data['cases'] if c['included']}
    api.require(isinstance(cfg.get('strengths'), list), 'coaching.strengths', '需要有据优点数组，可为空')
    api.require(isinstance(cfg.get('plans'), list) and len(cfg['plans']) <= 3, 'coaching.plans', '最多三个训练重点')
    plan_ids = set()
    for item in cfg['strengths'] + cfg['plans']:
        ids = item.get('case_ids')
        api.require(isinstance(ids, list) and ids and len(ids) == len(set(ids)) and set(ids) <= set(cases), 'coaching.case_ids', '依据必须为本销售当前纳入案，不可跨批或重复')
    for item in cfg['strengths']:
        api.string(item.get('claim'), 'coaching.strengths.claim')
    for plan in cfg['plans']:
        pid = api.string(plan.get('id'), 'coaching.plan.id')
        api.require(pid not in plan_ids, 'coaching.plan.id', '计划ID重复')
        plan_ids.add(pid)
        api.choice(plan.get('layer'), LAYERS, 'coaching.plan.layer')
        for key in ('skill', 'action', 'exercise', 'pass_criteria', 'next_review'):
            api.string(plan.get(key), 'coaching.plan.' + key)
        api.require(plan.get('status') == 'proposed', 'coaching.plan.status', '未发生训练只能记建议')
        api.require(isinstance(plan.get('source_paths'), list) and bool(plan['source_paths']), 'coaching.plan.source_paths', '训练需有依据')
        for path in plan['source_paths']:
            source_text(path, api)
    for c in cases.values():
        path = c['id'] + '.layers'
        layers = api.obj(c['management'].get('layers'), path)
        messages = {x['id']: x for x in c['source_messages']}
        def refs(value, needed=False):
            api.require(isinstance(value, list) and len(value) == len(set(value)), path + '.refs', '引用数组不可重复')
            api.require(not needed or bool(value), path + '.refs', '可见缺口或良好表现需要本案证据')
            for ref in value:
                api.require(ref in messages, path + '.refs', '引用不存在或来自其他案例')
                api.require(not messages[ref].get('sensitive') and bool(messages[ref]['text'].strip()), path + '.refs', '敏感或空白消息不得引用')
        api.choice(layers.get('primary'), PRIMARY, path + '.primary')
        for key in LAYERS:
            layer = api.obj(layers.get(key), path + '.' + key)
            api.choice(layer.get('status'), STATES, path + '.' + key + '.status')
            api.string(layer.get('finding'), path + '.' + key + '.finding')
            if key != 'execution':
                api.string(layer.get('expected'), path + '.' + key + '.expected')
            refs(layer.get('refs'), layer['status'] in ('gap', 'sound'))
        j, x, ex = (layers[k]['status'] == 'gap' for k in LAYERS)
        primary = layers['primary']
        api.require(primary != 'both' or (j and x), path, '两层均有缺口须分别有据')
        api.require(primary != 'judgment' or j, path, '判断主问题与第一层不一致')
        api.require(primary != 'expression' or (x and not j), path, '第一层存在缺口时不能只标表达')
        api.require(primary != 'execution' or ex, path, '执行主问题与执行标签不一致')
        api.require(primary not in ('none', 'unknown') or not (j or x or ex), path, '可见缺口不可同时标无缺口或未知')
        api.string(layers.get('causal_limit'), path + '.causal_limit')
        library = layers.get('library')
        api.require(isinstance(library, list), path + '.library', '需明确来源数组')
        api.require(not (j or x or ex) or bool(library), path + '.library', '明确销售缺口需要相关教学依据')
        for item in library:
            api.choice(item.get('source_kind'), ('scene', 'training_rule'), path + '.source_kind')
            text = source_text(item.get('path'), api)
            if item['source_kind'] == 'scene':
                api.require(item['path'].startswith('references/scenes/'), path + '.source_kind', '原话术来源必须在场景库')
            for key in ('locator', 'quote', 'rationale'):
                api.string(item.get(key), path + '.library.' + key)
            api.require(len(canonical(item['quote'])) >= 8 and canonical(item['quote']) in canonical(text), path + '.library.quote', '摘录不在对应来源原文中或过短')
            if item['source_kind'] == 'scene':
                number = re.search(r'(?:第|场景)?\s*(\d{1,2})\s*(?:条|号|[｜|：:])', item['locator'])
                api.require(number is not None, path + '.library.locator', '场景定位须明确编号，例如第22条或22｜标题')
                blocks = re.split(r'(?m)^##\s+(\d{2})[｜|]', text)
                sections = {int(blocks[i]): blocks[i + 1] for i in range(1, len(blocks), 2)}
                block = sections.get(int(number.group(1)), '')
                api.require(canonical(item['quote']) in canonical(block), path + '.library.locator', '摘录与指定场景编号不一致')
                original = '\n'.join(line for line in block.splitlines() if line.lstrip().startswith('>') or line.lstrip().startswith('*原库提示'))
                api.require(canonical(item['quote']) in canonical(original), path + '.library.quote', 'scene只能引用原库引文/提示；运行说明请标training_rule而非原话术')
            api.choice(item.get('layer'), LAYERS, path + '.library.layer')
            api.choice(item.get('application'), APPLICATION, path + '.library.application')
            refs(item.get('refs'), item['application'] not in ('unknown', 'not_applicable'))
        training = api.obj(layers.get('training'), path + '.training')
        api.choice(training.get('kind'), TRAINING, path + '.training.kind')
        for key in ('action', 'exercise', 'pass_criteria'):
            api.string(training.get(key), path + '.training.' + key)
        api.require(training.get('status') == 'proposed', path + '.training.status', '未发生训练只能记建议')
    return data


def overview(data, api):
    e = api.e
    cfg = data['management']['coaching']
    cases = [c for c in data['cases'] if c['included']]
    byid = {c['id']: c for c in cases}
    def links(items):
        return '<div class="case-links">' + ''.join(f'<button type="button" data-case="{e(c["id"])}"><span>{e(c["name"])} · {e(c["id"])}</span><small>{e(c["management"]["layers"]["primary"] and PRIMARY[c["management"]["layers"]["primary"]])} →</small></button>' for c in items) + '</div>'
    rows = []
    for key, title in LAYERS.items():
        counts = Counter(c['management']['layers'][key]['status'] for c in cases)
        items = [c for c in cases if c['management']['layers'][key]['status'] == 'gap']
        body = links(items) if items else '<p>本批未见可明确指认的缺口。</p>'
        rows.append(f'<details><summary><b>{e(title)}</b>：{counts["gap"]}案有可见缺口</summary><p class="muted">未见明显缺口{counts["sound"]}案；证据不足{counts["unknown"]}案；不适用{counts["not_applicable"]}案。</p>{body}</details>')
    strengths = ''.join(f'<p>{e(x["claim"])}</p>{links([byid[cid] for cid in x["case_ids"]])}' for x in cfg['strengths'])
    plans = []
    for p in cfg['plans']:
        plans.append(f'<details><summary><b>{e(LAYERS[p["layer"]])}：{e(p["skill"])}</b></summary><p><b>安排：</b>{e(p["action"])}</p><p><b>怎么练：</b>{e(p["exercise"])}</p><p><b>验收：</b>{e(p["pass_criteria"])}</p><p class="muted">下一次观察：{e(p["next_review"])}</p>{links([byid[cid] for cid in p["case_ids"]])}</details>')
    baseline = '校正后的首次观察；上一批混入数据已作废，不参与趋势。' if cfg['basis'] == 'corrected_baseline' else '当前观察基线；尚无可比较的训练后表现。'
    return f'''<section class="panel" id="coaching-overview"><h2>两层复盘 · 先判断，再表达</h2><p class="muted">截至最新资料，覆盖本批{len(cases)}案。同案可在两层分别有缺口，人数不相加；执行兑现另列，未成交不等于销售有错。</p>{''.join(rows)}<details><summary>值得保留的做法</summary>{strengths or '<p>本批证据尚不足以单独归纳稳定优势。</p>'}</details><h3>本次带教行动 · 建议，尚未执行</h3>{''.join(plans)}<details><summary>持续观察与岗位判断边界</summary><p>{e(baseline)}</p><p>{e(cfg['assessment'])}</p><p>训练是否执行、下一批同类表现与业务结果尚待记录。当前不据此给出淘汰结论。原始资料与观察文件仍遵守现有保留期限，不作永久记忆承诺。</p></details></section>'''


def detail(case, api):
    e = api.e
    layers = case['management']['layers']
    rows = []
    for key, label in LAYERS.items():
        item = layers[key]
        expected = f'<p><b>合理做法：</b>{e(item["expected"])}</p>' if key != 'execution' else ''
        quotes = ''.join(api.quote(case, ref) for ref in item['refs'])
        rows.append(f'<details><summary><b>{label}</b> · {STATES[item["status"]]}</summary><p>{e(item["finding"])}</p>{expected}{quotes}</details>')
    sources = []
    for item in layers['library']:
        quotes = ''.join(api.quote(case, ref) for ref in item['refs'])
        source_label = '原话术库逐字摘录' if item['source_kind'] == 'scene' else 'Skill运行规则（非原话术逐字）'
        sources.append(f'<details><summary>{e(item["locator"])} · {e(APPLICATION[item["application"]])}</summary><p><span class="badge">{source_label}</span> {e(LAYERS[item["layer"]])}</p><p class="muted">{e(item["path"])}</p><blockquote class="quote">{e(item["quote"])}</blockquote><p><b>本案对应：</b>{e(item["rationale"])}</p>{quotes}</details>')
    tr = layers['training']
    return f'''<div class="analysis-node two-layer"><h3>两层结论：{e(PRIMARY[layers['primary']])}</h3>{''.join(rows)}<p class="muted">{e(layers['causal_limit'])}</p><details class="library-mapping"><summary>对应培训与原话术 · {len(sources)}处</summary>{''.join(sources) or '<p>缺证或本案不适用，未强行指定背诵段落。</p>'}</details><details><summary>本案训练：{e(TRAINING[tr['kind']])} · 待执行</summary><p><b>练什么：</b>{e(tr['action'])}</p><p><b>怎么练：</b>{e(tr['exercise'])}</p><p><b>怎样算通过：</b>{e(tr['pass_criteria'])}</p></details></div>'''


def observation(data, source):
    """Export a private baseline with stable source identity, no customer transcript."""
    raw = source['cases'] if isinstance(source, dict) else source
    byid = {c['id']: c for c in raw}
    cfg = data['management']['coaching']
    observations = []
    for c in data['cases']:
        if not c['included']:
            continue
        rawcase = byid[c['id']]
        stable = hashlib.sha256((rawcase['account_id'] + '\x1f' + rawcase['user_id']).encode('utf-8')).hexdigest()
        snapshot = hashlib.sha256(json.dumps([(m['time'], m['source_role'], m['text']) for m in c['source_messages']], ensure_ascii=False).encode('utf-8')).hexdigest()
        layers = c['management']['layers']
        observations.append({'case_key': stable, 'batch_case_id': c['id'], 'snapshot_sha256': snapshot,
                             'primary': layers['primary'], 'states': {key: layers[key]['status'] for key in LAYERS},
                             'plan_ids': [p['id'] for p in cfg['plans'] if c['id'] in p['case_ids']],
                             'training_status': 'proposed', 'change_from_prior': None})
    return {'schema_version': 'skill3-coaching-observation/1', 'sales': data['sales'],
            'basis': cfg['basis'], 'previous_batch_status': cfg['previous_batch_status'],
            'period': {k: data['management'][k] for k in ('week_start', 'week_end', 'cutoff', 'time_basis')},
            'source_files': sorted({m['source'] for c in data['cases'] for m in c['source_messages']}),
            'counts': {key: dict(Counter(c['management']['layers'][key]['status'] for c in data['cases'] if c['included'])) for key in LAYERS},
            'training_plans': cfg['plans'], 'cases': observations,
            'human_review': 'pending', 'training_completed': None, 'improvement': None,
            'retention': '沿用本批客户资料保留期限，未授权永久保存或自动作人事决定'}
