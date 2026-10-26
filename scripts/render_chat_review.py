#!/usr/bin/env python3
"""Validate and render one salesperson's evidence-based local chat review.

Standard library only. No business judgments, stages, payments, or scripts are
inferred here. Real customer data must stay outside the Skill/repository.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import html
import json
from pathlib import Path
import re
import sys

STAGES = {"reception": "承接", "diagnosis": "诊断", "proposal": "方案报价",
          "objection": "异议处理", "close": "Close"}
STEPS = {1: "STEP 1｜承接 + 快速诊断", 2: "STEP 2｜诊断式 Presentation + 方案 + 报价",
         3: "STEP 3｜异议定位 + Convince", 4: "STEP 4｜成交路径判断 + Close",
         5: "STEP 5｜进入对应下一阶段"}
GROUPS = {"rescue": "重点补救", "trial_followup": "正常首课跟进",
          "order_check": "仅订单核实", "routine": "正常推进",
          "historical": "历史复盘", "low_priority": "暂不逐案详谈", "excluded": "不纳入"}
VALIDITY = {"high": "优质有效", "effective": "基础有效", "pending": "待判定",
            "scope_unknown": "范围待核", "invalid": "无效"}
FORMAL = {"confirmed": "正式成交已确认", "not_confirmed": "截至记录未确认正式成交",
          "unknown": "正式成交待核"}
FIRST = {"paid": "首课已付费", "completed": "首课已完成", "accepted": "已接受首课，付款待核",
         "not_started": "未进入首课", "unknown": "首课状态待核"}
POSSIBILITY = {"recoverable": "当前可推进", "conditional": "有条件可推进",
               "not_now": "当前不宜推进原需求", "no_contact": "停止该渠道触达", "unknown": "先核实"}
NATURE = {"gap": "尚未解决", "established": "已有共识", "unknown": "证据不足", "not_applicable": "本案不适用"}
BRANCH = {"formal": "正式购买", "trial": "首课支线", "transfer": "转接支线", "none": ""}
ID_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,79}\Z")


class ValidationError(ValueError):
    pass


def require(ok, path, message):
    if not ok:
        raise ValidationError(f"{path}：{message}")


def obj(value, path):
    require(isinstance(value, dict), path, "应为对象")
    return value


def field(value, key, path):
    require(key in value, f"{path}.{key}", "缺少必填字段；未知事实应明确写 unknown/null，不能省略后按零处理")
    return value[key]


def string(value, path, empty=False):
    require(isinstance(value, str), path, "应为文本")
    require(empty or bool(value.strip()), path, "不能为空")
    return value


def choice(value, allowed, path):
    require(isinstance(value, str) and value in allowed, path, "只允许：" + ", ".join(allowed))


def number(value, path):
    require(isinstance(value, (str, int, float)) and not isinstance(value, bool), path, "应为确知数值")
    try:
        value = Decimal(str(value))
    except InvalidOperation:
        raise ValidationError(path + "：金额不能解析")
    require(value.is_finite() and value >= 0, path, "应为有限非负数")
    return value


def validate(data):
    obj(data, "报告")
    require(field(data, "schema_version", "报告") == "1.0", "schema_version", "只支持 1.0")
    sales = obj(field(data, "sales", "报告"), "sales")
    sid = string(field(sales, "id", "sales"), "sales.id")
    string(field(sales, "name", "sales"), "sales.name")
    period = obj(field(data, "period", "报告"), "period")
    for key in ("start", "end", "cutoff"):
        string(field(period, key, "period"), "period." + key)
    scope = obj(field(data, "scope", "报告"), "scope")
    choice(field(scope, "cohort", "scope"), ("new_clients", "active_conversations", "unknown"), "scope.cohort")
    string(field(scope, "coverage", "scope"), "scope.coverage")
    require(type(field(scope, "orders_complete", "scope")) is bool, "scope.orders_complete", "必须明确 true/false")
    targets = obj(field(data, "targets", "报告"), "targets")
    conversion_target = field(targets, "conversion_rate", "targets")
    if conversion_target is not None:
        require(number(conversion_target, "targets.conversion_rate") <= 1, "targets.conversion_rate", "应在 0 到 1 之间")
    receipt_target = field(targets, "average_order_rmb", "targets")
    if receipt_target is not None:
        number(receipt_target, "targets.average_order_rmb")
    standards = field(data, "standards", "报告")
    require(isinstance(standards, list), "standards", "应为文本数组")
    for i, item in enumerate(standards):
        string(item, f"standards[{i}]")
    cases = field(data, "cases", "报告")
    require(isinstance(cases, list) and cases, "cases", "需要至少一个案例")
    case_ids, message_owners, locators = set(), {}, set()
    for i, case in enumerate(cases):
        p = f"cases[{i}]"
        obj(case, p)
        cid = string(field(case, "id", p), p + ".id")
        require(bool(ID_PATTERN.fullmatch(cid)), p + ".id", "使用字母开头的编号，仅字母、数字、下划线和短横线")
        require(cid not in case_ids, p + ".id", "案例编号重复")
        case_ids.add(cid)
        require(field(case, "sales_id", p) == sid, p + ".sales_id", "同一报告只能包含一位销售，请拆分文件")
        for key in ("name", "date"):
            string(field(case, key, p), p + "." + key)
        included = field(case, "included", p)
        require(type(included) is bool, p + ".included", "必须明确 true/false")
        choice(field(case, "group", p), GROUPS, p + ".group")
        require((case["group"] != "excluded") == included, p + ".group", "不纳入案例必须归 excluded，纳入案例不得归 excluded")
        string(field(case, "exclusion_reason", p), p + ".exclusion_reason", empty=included)
        messages = field(case, "source_messages", p)
        require(isinstance(messages, list) and messages, p + ".source_messages", "需要可追溯的本案消息")
        own_ids, sensitive, empty_messages = set(), set(), set()
        for j, message in enumerate(messages):
            mp = f"{p}.source_messages[{j}]"
            obj(message, mp)
            mid = string(field(message, "id", mp), mp + ".id")
            require(bool(ID_PATTERN.fullmatch(mid)), mp + ".id", "消息编号格式与案例编号相同，建议以案例编号开头")
            require(mid not in message_owners, mp + ".id", "消息编号重复；原话不能跨案复用")
            message_owners[mid] = cid
            own_ids.add(mid)
            for key in ("source", "sheet", "time", "speaker", "text"):
                string(field(message, key, mp), mp + "." + key, empty=key in ("sheet", "text"))
            if not message["text"].strip():
                empty_messages.add(mid)
            row = field(message, "row", mp)
            require(row is None or (type(row) is int and row > 0), mp + ".row", "应为正整数原始行号，无行号截图使用 null")
            if row is not None:
                loc = (message["source"], message["sheet"], row)
                require(loc not in locators, mp + ".row", "同一源文件/工作表/行号已重复归属，先处理归属再渲染")
                locators.add(loc)
            if "sensitive" in message:
                require(type(message["sensitive"]) is bool, mp + ".sensitive", "必须为 true/false")
            if message.get("sensitive"):
                sensitive.add(mid)

        def refs(value, rp, nonempty=True):
            require(isinstance(value, list), rp, "应为消息编号数组")
            require(not nonempty or bool(value), rp, "需要本案原话依据")
            require(all(isinstance(v, str) for v in value), rp, "引用必须为文本编号")
            require(len(value) == len(set(value)), rp, "重复引用")
            for ref in value:
                require(ref in own_ids, rp, f"{ref!r} 不属于本案或不存在，不能跨案例引用")
                require(ref not in sensitive, rp, "无关敏感消息不能作为复盘依据或引用正文，请移除引用而非改写原消息")
                require(ref not in empty_messages, rp, "空白原消息不能作为判断引用")

        if not included:
            continue
        validity = obj(field(case, "validity", p), p + ".validity")
        choice(field(validity, "status", p + ".validity"), VALIDITY, p + ".validity.status")
        string(field(validity, "reason", p + ".validity"), p + ".validity.reason")
        refs(field(validity, "refs", p + ".validity"), p + ".validity.refs")
        order = obj(field(case, "order", p), p + ".order")
        choice(field(order, "formal", p + ".order"), FORMAL, p + ".order.formal")
        choice(field(order, "first_lesson", p + ".order"), FIRST, p + ".order.first_lesson")
        string(field(order, "summary", p + ".order"), p + ".order.summary")
        refs(field(order, "refs", p + ".order"), p + ".order.refs")
        if scope["orders_complete"]:
            require(order["formal"] != "unknown", p + ".order.formal", "订单覆盖完整与正式成交待核矛盾")
        for key in ("actual_receipts", "quotes"):
            values = field(order, key, p + ".order")
            require(isinstance(values, list), p + ".order." + key, "应为数组；未知金额用空数组，不填零")
            for j, value in enumerate(values):
                vp = f"{p}.order.{key}[{j}]"
                obj(value, vp)
                number(field(value, "amount", vp), vp + ".amount")
                string(field(value, "currency", vp), vp + ".currency")
                refs(field(value, "refs", vp), vp + ".refs")
                if key == "actual_receipts":
                    choice(field(value, "kind", vp), ("formal", "trial", "unknown"), vp + ".kind")
                    if value["kind"] == "formal":
                        require(order["formal"] == "confirmed", vp + ".kind", "正式实收与未确认正式成交矛盾")
                else:
                    string(field(value, "description", vp), vp + ".description")
        phases = obj(field(case, "phases", p), p + ".phases")
        require(set(phases) == set(STAGES), p + ".phases", "必须且只能包含固定五列")
        for key in STAGES:
            pp = p + ".phases." + key
            phase = obj(phases[key], pp)
            choice(field(phase, "state", pp), ("done", "gap", "not_done", "unknown"), pp + ".state")
            string(field(phase, "reason", pp), pp + ".reason")
            refs(field(phase, "refs", pp), pp + ".refs", nonempty=phase["state"] in ("done", "gap"))
            choice(field(phase, "branch", pp), BRANCH, pp + ".branch")
            require(key == "close" or phase["branch"] == "none", pp + ".branch", "支线标签只用于 Close")
        position = obj(field(case, "position", p), p + ".position")
        for key in ("furthest", "current"):
            pp = p + ".position." + key
            node = obj(field(position, key, p + ".position"), pp)
            step = field(node, "step", pp)
            require(step is None or (type(step) is int and step in STEPS), pp + ".step", "应为培训 STEP 1—5 或 null")
            choice(field(node, "branch", pp), BRANCH, pp + ".branch")
            string(field(node, "reason", pp), pp + ".reason")
            refs(field(node, "refs", pp), pp + ".refs", nonempty=step is not None)
        main_stage = field(position, "main_stage", p + ".position")
        require(main_stage is None or isinstance(main_stage, str) and main_stage in STAGES, p + ".position.main_stage", "只能用固定五列编号或 null，交付/排课/资料不足不是第六阶段")
        for key in ("scene", "reason"):
            string(field(position, key, p + ".position"), p + ".position." + key, empty=key == "scene")
        for key in ("headline", "goal", "current_problem", "attribution", "opportunity", "other_constraints"):
            string(field(case, key, p), p + "." + key, empty=key == "other_constraints")
        refs(field(case, "summary_refs", p), p + ".summary_refs")
        require(len(case["summary_refs"]) <= 3, p + ".summary_refs", "总表最多三条关键原话，完整证据放详情")
        nature = field(case, "nature", p)
        require(isinstance(nature, list) and len(nature) == 3, p + ".nature", "分别判断三性，不能省略后假定没问题")
        for j, item in enumerate(nature):
            obj(item, f"{p}.nature[{j}]")
            string(field(item, "name", f"{p}.nature[{j}]"), f"{p}.nature[{j}].name")
        require({item["name"] for item in nature} == {"重要性", "有效性", "紧迫性"}, p + ".nature", "三性名称必须各出现一次")
        for j, item in enumerate(nature):
            np = f"{p}.nature[{j}]"
            choice(field(item, "state", np), NATURE, np + ".state")
            string(field(item, "reason", np), np + ".reason")
            refs(field(item, "refs", np), np + ".refs", nonempty=item["state"] in ("gap", "established"))
        nodes = field(case, "evidence_nodes", p)
        require(isinstance(nodes, list), p + ".evidence_nodes", "应为证据链数组")
        require(bool(nodes) or case["group"] not in ("rescue", "historical"), p + ".evidence_nodes", "补救/历史复盘需要原话→问题→影响→改法")
        for j, node in enumerate(nodes):
            np = f"{p}.evidence_nodes[{j}]"
            obj(node, np)
            refs(field(node, "refs", np), np + ".refs")
            for key in ("missed", "impact", "better", "limit"):
                string(field(node, key, np), np + "." + key)
        recovery = obj(field(case, "recovery", p), p + ".recovery")
        choice(field(recovery, "possibility", p + ".recovery"), POSSIBILITY, p + ".recovery.possibility")
        for key in ("reason", "script", "script_conditions", "coaching_question", "next_signal"):
            string(field(recovery, key, p + ".recovery"), p + ".recovery." + key, empty=key in ("script", "script_conditions"))
        actions = field(recovery, "actions", p + ".recovery")
        require(isinstance(actions, list) and actions, p + ".recovery.actions", "至少给一个动作，可为内部核实或停止触达")
        for j, action in enumerate(actions):
            ap = f"{p}.recovery.actions[{j}]"
            obj(action, ap)
            for key in ("owner", "action", "when", "signal"):
                string(field(action, key, ap), ap + "." + key)
        if case["group"] == "rescue" and recovery["possibility"] in ("recoverable", "conditional"):
            string(recovery["script"], p + ".recovery.script")
            string(recovery["script_conditions"], p + ".recovery.script_conditions")
        if recovery["possibility"] == "no_contact":
            require(not recovery["script"].strip(), p + ".recovery.script", "停止触达的案例不能继续提供推销话术")
        if case["group"] == "trial_followup":
            require(order["first_lesson"] in ("paid", "completed", "accepted"), p + ".group", "正常首课跟进需有首课支线依据")
        if case["group"] == "order_check":
            require(order["formal"] == "unknown" or order["first_lesson"] == "unknown", p + ".group", "仅订单核实应明确哪项订单事实未知")
    require(any(c["included"] for c in cases), "cases", "没有纳入案例，不能生成客户复盘")
    return data


def verify_source(data, source):
    """Compare unmodified messages against a separately extracted source file."""
    cases = source.get("cases") if isinstance(source, dict) else source
    require(isinstance(cases, list), "--source", "应为导入器案例数组，或含 cases 数组的对象")
    by_id = {}
    for case in cases:
        obj(case, "--source.case")
        cid = string(field(case, "id", "--source.case"), "--source.case.id")
        require(cid not in by_id, "--source", "源案例编号重复")
        by_id[cid] = case
    checked = 0
    for case in data["cases"]:
        p = "--source." + case["id"]
        require(case["id"] in by_id, p, "原始提取数据没有本案编号")
        raw = by_id[case["id"]]
        if raw.get("account_id") is not None:
            require(raw["account_id"] == case["sales_id"], p, "销售账号与原始提取归属不一致")
        raw_messages = field(raw, "messages", p)
        require(isinstance(raw_messages, list), p + ".messages", "应为消息数组")
        indexed = {}
        for message in raw_messages:
            obj(message, p + ".messages")
            loc = (message.get("source_sheet", message.get("sheet", "")),
                   message.get("source_row", message.get("row")))
            require(loc not in indexed, p, "原始提取的工作表/行号重复，无法唯一核对")
            indexed[loc] = message
        for message in case["source_messages"]:
            loc = (message["sheet"], message["row"])
            require(loc in indexed, p + "." + message["id"], "原始提取中没有同案、同工作表、同行号")
            original = indexed[loc]
            for key in ("text", "time"):
                require(message[key] == original.get(key), p + "." + message["id"] + "." + key,
                        "与独立源文件不一致；不能改写原话或时间后仍称逐字引用")
            original_role = original.get("role", original.get("speaker"))
            require(original_role is not None, p + "." + message["id"], "独立源缺少 role/speaker")
            require(message.get("source_role", message["speaker"]) == original_role,
                    p + "." + message["id"] + ".speaker", "说话角色与独立源不一致；显示名不同可显式提供 source_role")
            checked += 1
    return checked


def private_output(path):
    resolved = path.resolve()
    skill_root = Path(__file__).resolve().parent.parent
    require(resolved != skill_root and skill_root not in resolved.parents, "--output", "客户复盘不能写进 Skill")
    require(".git" not in resolved.parts, "--output", "客户复盘不能写进 .git")
    for ancestor in (resolved.parent, *resolved.parent.parents):
        require(not (ancestor / ".git").exists(), "--output", "客户复盘不能写进 Git 工作区，请指定私有客户目录")


def e(value):
    return html.escape(str(value), quote=True)


def lines(value):
    return e(value).replace("\n", "<br>")


def stats(data):
    cases = [c for c in data["cases"] if c["included"]]
    return {"contacts": len(data["cases"]), "included": len(cases), "excluded": len(data["cases"]) - len(cases),
            "effective": sum(c["validity"]["status"] in ("high", "effective") for c in cases),
            "validity": dict(Counter(c["validity"]["status"] for c in cases)),
            "groups": {k: sum(c["group"] == k for c in cases) for k in GROUPS if k != "excluded"},
            "formal_confirmed": sum(c["order"]["formal"] == "confirmed" for c in cases),
            "formal_unknown": sum(c["order"]["formal"] == "unknown" for c in cases),
            "trial_paid_or_completed": sum(c["order"]["first_lesson"] in ("paid", "completed") for c in cases)}


def quote(case, mid, compact=False):
    m = next(m for m in case["source_messages"] if m["id"] == mid)
    location = m["source"] + (" / " + m["sheet"] if m["sheet"] else "")
    if m["row"] is not None:
        location += " · 第" + str(m["row"]) + "行"
    body = "［无关敏感内容已隐藏］" if m.get("sensitive") else m["text"]
    cls = "quote compact" if compact else "quote"
    return f'<div class="{cls}"><div class="quote-meta"><b>{e(m["speaker"])}</b><span>{e(m["time"])}</span></div><blockquote>{lines(body)}</blockquote><small>{e(location)} · {e(mid)}</small></div>'


def phase_cell(phase):
    state = phase["state"]
    value = "✓" if state in ("done", "gap") else ("待核" if state == "unknown" else "")
    note = "<small>" + lines(phase["reason"]) + "</small>" if state == "gap" else ""
    branch = "<small class=branch>" + e(BRANCH[phase["branch"]]) + "</small>" if phase["branch"] in ("trial", "transfer") and state in ("done", "gap") else ""
    label = {"done": "已完成", "gap": "已完成但有不足", "not_done": "未完成", "unknown": "记录不足"}[state]
    return f'<td class="phase {state}" title="{e(phase["reason"])}" aria-label="{label}"><b>{value}</b>{note}{branch}</td>'


def stage_label(value):
    return STAGES[value] if value else "无明确缺口／阶段待核"


def step_card(node, label):
    branch = BRANCH[node["branch"]]
    return f'<div><small>{label}</small><strong>{e(STEPS.get(node["step"], "阶段待核"))}</strong><b class="branch">{e(branch)}</b><p>{lines(node["reason"])}</p><small>依据：{e("、".join(node["refs"])) or "证据不足"}</small></div>'


def detail(case):
    cid, p, r, order = case["id"], case["position"], case["recovery"], case["order"]
    nature = ''.join(f'<div class="nature {e(n["state"])}"><b>{e(n["name"])} · {e(NATURE[n["state"]])}</b><p>{lines(n["reason"])}</p><small>依据：{e("、".join(n["refs"])) or "未取得可判依据"}</small></div>' for n in case["nature"])
    nodes = []
    for index, node in enumerate(case["evidence_nodes"], 1):
        nodes.append(f'<section class="evidence-node"><h3>{index}．看原话，定位这一处断点</h3>' + ''.join(quote(case, mid) for mid in node["refs"]) +
                     f'<div class="cause"><h4>这段咨询没完成什么</h4><p>{lines(node["missed"])}</p><h4>为什么会影响购买</h4><p>{lines(node["impact"])}</p><h4>当时更好的接法</h4><p>{lines(node["better"])}</p><p class="limit"><b>判断边界：</b>{lines(node["limit"])}</p></div></section>')
    actions = ''.join(f'<li><b>{e(a["owner"])}</b> · {lines(a["action"])}<small>什么时候：{lines(a["when"])}<br>做到什么算推进：{lines(a["signal"])}</small></li>' for a in r["actions"])
    amounts = []
    for key, label in (("actual_receipts", "已核实收"), ("quotes", "报价，不能当实收")):
        for item in order[key]:
            description = item.get("description", {"formal": "正式", "trial": "首课", "unknown": "订单性质待核"}.get(item.get("kind"), ""))
            amounts.append(f'<li><b>{label}：</b>{e(item["amount"])} {e(item["currency"])} · {e(description)}<small>依据：{e("、".join(item["refs"]))}</small></li>')
    amounts_html = '<ul class="amounts">' + ''.join(amounts) + '</ul>' if amounts else '<p class="muted">实收金额未核，不将报价或付款意愿记为收入。</p>'
    script = f'<div class="script"><h3>建议话术 · 未发送</h3><p class="condition">使用前提：{lines(r["script_conditions"])}</p><div class="message-draft">{lines(r["script"])}</div></div>' if r["script"] else '<p class="muted">本次先执行上面的内部动作，没有可直接发送的客户稿。</p>'
    referenced = set(case["summary_refs"] + case["validity"]["refs"] + order["refs"])
    for phase in case["phases"].values():
        referenced.update(phase["refs"])
    for n in case["nature"]:
        referenced.update(n["refs"])
    for key in ("furthest", "current"):
        referenced.update(p[key]["refs"])
    for key in ("actual_receipts", "quotes"):
        for item in order[key]:
            referenced.update(item["refs"])
    for node in case["evidence_nodes"]:
        referenced.update(node["refs"])
    references = ''.join(quote(case, m["id"]) for m in case["source_messages"] if m["id"] in referenced)
    return f'''<article id="{e(cid)}" class="case-detail" data-case="{e(cid)}">
<header><span class="tag {e(case['group'])}">{e(GROUPS[case['group']])}</span><h2>{e(cid)} · {e(case['name'])}</h2><p class="headline">{lines(case['headline'])}</p><p class="goal"><b>本次拿单／复盘目标：</b>{lines(case['goal'])}</p></header>
<section><h3>成交与首课分开看</h3><p><b>{e(FORMAL[order['formal']])}</b>；{e(FIRST[order['first_lesson']])}</p><p>{lines(order['summary'])}</p>{amounts_html}</section>
<div class="position-grid">{step_card(p['furthest'], '最远走到')}{step_card(p['current'], '现在需要解决')}</div>
<p><b>主要问题阶段：</b>{e(stage_label(p['main_stage']))}。{lines(p['reason'])}</p><p class="muted">业务场景：{lines(p['scene']) or '未单列'}</p><p class="main-problem"><b>真正卡住的地方：</b>{lines(case['current_problem'])}</p><p><b>归因与精力安排：</b>{lines(case['attribution'])}</p>
<div class="nature-grid">{nature}</div><p><b>三性之外的实际约束：</b>{lines(case['other_constraints']) or '当前未发现已证实的额外约束。'}</p>
{''.join(nodes)}<section class="opportunity"><h3>为什么值得争取，离成交还差什么</h3><p>{lines(case['opportunity'])}</p></section><section class="recovery"><h3>接下来还能不能争取</h3><p><b>{e(POSSIBILITY[r['possibility']])}：</b>{lines(r['reason'])}</p><ol>{actions}</ol>{script}<div class="coaching"><h3>与销售一起复盘时问</h3><p>{lines(r['coaching_question'])}</p><p><b>下一次看到什么，才算向成交推进：</b>{lines(r['next_signal'])}</p></div></section>
<details><summary>有效性、阶段和订单的原话依据</summary><p><b>{e(VALIDITY[case['validity']['status']])}：</b>{lines(case['validity']['reason'])}</p><p>有效性依据：{e('、'.join(case['validity']['refs']))}；订单依据：{e('、'.join(order['refs']))}</p>{references}</details><a class="back" href="#overview">回谈单总表 ↑</a></article>'''


SCRIPT = r'''(() => {
const rows=[...document.querySelectorAll('[data-review-row]')];
const cards=[...document.querySelectorAll('[data-case]')];
const group=document.getElementById('group-filter'), stage=document.getElementById('stage-filter'), search=document.getElementById('search');
function filter(){let n=0;for(const row of rows){const ok=(!group.value||row.dataset.group===group.value)&&(!stage.value||row.dataset.stage===stage.value)&&row.dataset.search.toLowerCase().includes(search.value.trim().toLowerCase());row.hidden=!ok;if(ok)n++;}document.getElementById('visible-count').textContent='显示 '+n+' 位';}
function select(){let id;try{id=decodeURIComponent(location.hash.slice(1));}catch(e){return;}const target=cards.find(c=>c.id===id);if(target){for(const c of cards)c.hidden=c!==target;document.getElementById('detail-label').textContent='正在查看 '+id;target.scrollIntoView({block:'start'});}else if(id==='overview'||!id){for(const c of cards)c.hidden=c!==cards[0];document.getElementById('detail-label').textContent='先看优先级最高的客户';}}
group.addEventListener('change',filter);stage.addEventListener('change',filter);search.addEventListener('input',filter);
document.getElementById('reset').addEventListener('click',()=>{group.value='';stage.value='';search.value='';filter();});
document.getElementById('show-all').addEventListener('click',()=>{for(const c of cards)c.hidden=false;document.getElementById('detail-label').textContent='显示全部个案';});
document.getElementById('print-current').addEventListener('click',()=>{document.body.classList.add('print-current');window.print();document.body.classList.remove('print-current');});
window.addEventListener('hashchange',select);filter();select();
})();'''


def render(data, css):
    counts = stats(data)
    cases = sorted((c for c in data["cases"] if c["included"]), key=lambda c: list(GROUPS).index(c["group"]))
    formal = str(counts["formal_confirmed"]) + " 位已确认" if counts["formal_confirmed"] else ("0 位" if data["scope"]["orders_complete"] else "正式单待核")
    if not data["scope"]["orders_complete"] and counts["formal_confirmed"]:
        formal += "，其余待核"
    group_cards = ''.join(f'<a class="group-stat {key}" href="#group-{key}"><strong>{counts["groups"][key]}</strong><span>{e(label)}</span></a>' for key, label in GROUPS.items() if key != "excluded")
    rows, nav = [], []
    for group, label in GROUPS.items():
        if group == "excluded":
            continue
        selected = [c for c in cases if c["group"] == group]
        links = ''.join(f'<a href="#{e(c["id"])}"><b>{e(c["id"])} · {e(c["name"])}</b><small>{lines(c["headline"])}</small></a>' for c in selected)
        nav.append(f'<section id="group-{group}"><h3>{e(label)} · {len(selected)} 位</h3>' + (links or '<p class="muted">本批没有</p>') + '</section>')
    for case in cases:
        p, order = case["position"], case["order"]
        nature = "、".join(n["name"] for n in case["nature"] if n["state"] == "gap") or "未证实三性缺口"
        rows.append(f'<tr data-review-row data-group="{e(case["group"])}" data-stage="{e(p["main_stage"] or "unknown")}" data-search="{e(case["id"] + " " + case["name"])}"><td>{e(case["date"])}</td><td><a href="#{e(case["id"])}"><b>{e(case["name"])}</b></a><small>{e(case["id"])} · {e(VALIDITY[case["validity"]["status"]])}</small><span class="tag {e(case["group"])}">{e(GROUPS[case["group"]])}</span></td><td class="outcome"><b>{e(FORMAL[order["formal"]])}</b><small>{e(FIRST[order["first_lesson"]])}</small><p>{lines(order["summary"])}</p></td>' + ''.join(phase_cell(case["phases"][key]) for key in STAGES) + f'<td><b>{e(stage_label(p["main_stage"]))}</b><small>{e(nature)}</small></td><td>{lines(case["current_problem"])}</td><td class="comparison">' + ''.join(quote(case, mid, True) for mid in case["summary_refs"]) + f'<a href="#{e(case["id"])}">看原因、补救与话术 →</a></td></tr>')
    validity_text = "；".join(f'{VALIDITY[key]} {counts["validity"].get(key, 0)}' for key in VALIDITY)
    valid = [c for c in cases if c["validity"]["status"] in ("high", "effective")]
    pending = any(c["validity"]["status"] in ("pending", "scope_unknown") for c in cases)
    if data["scope"]["cohort"] == "new_clients" and data["scope"]["orders_complete"] and not pending and valid:
        numerator = sum(c["order"]["formal"] == "confirmed" for c in valid)
        kpi = f'本批新客有效分母与订单均已核齐，正式成交 {numerator}/{len(valid)}，转化率 {numerator/len(valid):.1%}。'
    else:
        kpi = '本批会话口径、有效性或订单覆盖不满足完整核算条件，不将已确认成交数除以有效客户数冒充绩效转化率。'
    excluded = [c for c in data["cases"] if not c["included"]]
    exclusion_html = ''.join(f'<li>{e(c["id"])} · {e(c["name"])}：{lines(c["exclusion_reason"])}</li>' for c in excluded) or '<li>本批没有排除项。</li>'
    title = data["sales"]["name"] + "客户复盘与补救报告"
    targets = data["targets"]
    conversion_display = "未设定" if targets["conversion_rate"] is None else f"{float(targets['conversion_rate']):.0%}"
    amount_display = "未设定" if targets["average_order_rmb"] is None else f"人民币 {targets['average_order_rmb']} 元"
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>{e(title)}</title><style>{css}</style></head><body>
<main><header class="report-header"><p class="eyebrow">先找到值得争取的单，再逐案带销售修正</p><h1>{e(title)}</h1><p>{e(data['period']['start'])} — {e(data['period']['end'])} · 截至 {e(data['period']['cutoff'])}</p><div class="stats"><div><strong>{counts['included']}</strong><span>纳入客户会话</span><small>{counts['contacts']} 个联系人，排除 {counts['excluded']} 个</small></div><div><strong>{counts['effective']}</strong><span>确定有效客户</span><small>待判定与范围待核不计有效分母</small></div><div><strong>{e(formal)}</strong><span>正式成交</span><small>首课不能代替正式购买</small></div><div><strong>{counts['trial_paid_or_completed']}</strong><span>已知付费／完成首课</span><small>未知订单性质另列核实</small></div></div></header>
<section class="priority"><h2>今天先把精力放在哪里</h2><div class="group-stats">{group_cards}</div><p>各组互斥，共 {counts['included']} 位。重点补救不是必然成交；正常首课、仅订单核实和历史案例不混入“销售丢掉的单”。</p></section>
<details class="scope"><summary>计数与判断口径</summary><p>{lines(data['scope']['coverage'])}</p><p>{e(validity_text)}</p><p>本次目标：有效客户正式转化 {e(conversion_display)}，正式订单平均实收 {e(amount_display)}。</p><p>{e(kpi)}</p><p>本版不根据收款笔数计算均单；分期款不等于多笔订单。完整订单人民币实收未核，不计算平均实收。</p><ul>{''.join('<li>'+lines(s)+'</li>' for s in data['standards'])}</ul><p>工具只核对结构、引用归属和展示一致性；销售判断及因果仍须负责人结合原话核验。</p></details>
<section id="overview"><h2>客户谈单总表</h2><p>先看成交状态，再看主要问题阶段。最远走到与当前卡点在个案中分别呈现，首课／转接 Close 单列支线。</p><div class="controls"><label>客户分组 <select id="group-filter"><option value="">全部</option>{''.join('<option value="'+key+'">'+e(label)+'</option>' for key,label in GROUPS.items() if key!='excluded')}</select></label><label>主要问题阶段 <select id="stage-filter"><option value="">全部</option>{''.join('<option value="'+key+'">'+e(label)+'</option>' for key,label in STAGES.items())}<option value="unknown">无明确缺口／阶段待核</option></select></label><label>找客户 <input id="search" type="search" placeholder="微信名或编号"></label><button type="button" id="reset">恢复全部</button><span id="visible-count" aria-live="polite"></span></div><p class="legend"><b>✓</b> 已完成且未见明显不足　<b>✓＋说明</b> 已完成但有不足　<b>空白</b> 未完成　<b>待核</b> 记录不足</p><div class="table-wrap"><table class="matrix"><thead><tr><th rowspan="2">日期</th><th rowspan="2">微信名</th><th rowspan="2">成交／跟进状态</th><th colspan="5">谈单阶段</th><th rowspan="2">主要问题阶段／性质</th><th rowspan="2">具体问题</th><th rowspan="2">聊天对照</th></tr><tr>{''.join('<th>'+e(s)+'</th>' for s in STAGES.values())}</tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section class="detail-toolbar"><h2>逐客谈清楚：卡点、证据、改法</h2><p id="detail-label"></p><button id="show-all" type="button">展开全部个案</button><button id="print-current" type="button">打印当前可见个案</button></section><div class="case-layout"><nav class="case-nav" aria-label="客户优先级导航">{''.join(nav)}</nav><div class="case-content">{''.join(detail(case) for case in cases)}</div></div><details class="exclusions"><summary>排除项与归属说明 · {len(excluded)} 个</summary><ul>{exclusion_html}</ul></details><footer>本地内部复盘资料。仅展示关键引用，不全量公开聊天。建议话术尚未发送；生成器不会联系客户或改变订单。</footer></main><script>{SCRIPT}</script></body></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description="校验并生成单销售离线复盘，不自动作业务判断")
    parser.add_argument("input", type=Path, help="符合 chat-review-data.md 的 JSON")
    parser.add_argument("--output", type=Path, help="HTML 路径，生成时必填")
    parser.add_argument("--check-only", action="store_true", help="只校验，不写入")
    parser.add_argument("--source", type=Path, help="独立导入器 cases.json，用于逐字核对消息与角色")
    parser.add_argument("--overwrite", action="store_true", help="已获明确覆盖授权时才使用")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        validate(data)
        management = None
        if "management" in data:
            import management_review as management
            management.validate(data, sys.modules[__name__])
        counts = stats(data)
        source_checked = None
        if args.source:
            source = json.loads(args.source.read_text(encoding="utf-8-sig"))
            source_checked = verify_source(data, source)
            if management:
                management.validate(data, sys.modules[__name__], source)
        if args.check_only:
            print(json.dumps({"valid": True, "sales": data["sales"]["name"], "source_messages_checked": source_checked, "counts": counts}, ensure_ascii=False))
            return 0
        require(args.output is not None, "--output", "生成时必须指定 HTML 路径")
        require(args.output.suffix.lower() == ".html", "--output", "扩展名必须为 .html")
        require(args.input.resolve() != args.output.resolve(), "--output", "不能覆盖输入数据")
        private_output(args.output)
        require(not args.output.exists() or args.overwrite, "--output", "文件已存在；默认不覆盖，已有授权才可加 --overwrite")
        css = (Path(__file__).resolve().parent.parent / "assets" / "chat-review.css").read_text(encoding="utf-8")
        result = management.render(data, sys.modules[__name__]) if management else render(data, css)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w" if args.overwrite else "x", encoding="utf-8", newline="\n") as handle:
            handle.write(result)
        print(json.dumps({"valid": True, "output": str(args.output), "source_messages_checked": source_checked, "counts": counts}, ensure_ascii=False))
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        print("无法生成复盘：" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
