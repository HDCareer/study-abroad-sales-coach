"""Deterministic business metrics; never infer order amounts from chat or revenue.

Only the business system supplies the accounting definitions and source values.
Amounts are calculated with Decimal and exported as finite JSON numbers. Missing
order coverage remains missing; this module does not alter sales judgments.
"""
import copy
from datetime import datetime
from decimal import Decimal, InvalidOperation
import math
import re
from management_review import validate_target_period


SCHEMA = 'skill3-supervisor-business/1.0'
RESULT_SCHEMA = 'skill3-supervisor-business-results/1.0'
DEFINITIONS = {
    'revenue': 'net_after_refunds',
    'conversion': 'period_first_formal_over_effective',
    'average_order': 'first_formal_order',
}


def require(ok, message):
    if not ok:
        raise ValueError('业务指标：' + message)


def text(value, path):
    require(isinstance(value, str) and bool(value.strip()), path + '须为非空文字')
    return value


def amount(value, path, *, nullable=False, nonnegative=False, positive=False):
    if value is None and nullable:
        return None
    require(type(value) in (int, float, Decimal), path + '须为数值；未知用null，不能用布尔或文字')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('业务指标：' + path + '不是有效金额') from None
    require(number.is_finite(), path + '必须有限，不能使用NaN或无穷值')
    require(not nonnegative or number >= 0, path + '不能为负')
    require(not positive or number > 0, path + '必须大于0，未设目标用null')
    require(abs(number) <= Decimal('9007199254740991'), path + '超出可安全展示的数值范围')
    return number


def count(value, path, nullable=False):
    if value is None and nullable:
        return None
    require(type(value) is int and 0 <= value <= 9007199254740991, path + '须为非负安全整数')
    return value


def number(value):
    if value is None:
        return None
    require(value.is_finite() and abs(value) <= Decimal('9007199254740991'), '计算结果超出可安全展示的有限数值范围')
    result = float(value)
    require(math.isfinite(result), '计算结果超出有限数字范围')
    return int(value) if value == value.to_integral_value() else result


def _window(finance_window, chat_window):
    require(isinstance(finance_window, dict) and isinstance(chat_window, dict), '需要明确业务与聊天统计窗口')
    parsed = []
    for label, window in [('业务', finance_window), ('聊天', chat_window)]:
        values = []
        for key in ('week_start', 'week_end', 'cutoff'):
            value = text(window.get(key), label + '.' + key)
            try:
                values.append(datetime.fromisoformat(value))
            except ValueError:
                raise ValueError('业务指标：' + label + '.' + key + '须为ISO时间') from None
        text(window.get('time_basis'), label + '.time_basis')
        parsed.append(values)
    try:
        fs, fe, fc = parsed[0]
        cs, ce, cc = parsed[1]
        require(fs <= fe <= fc, '业务统计起止/截止顺序错误')
        require(cs <= ce <= cc, '聊天统计起止/截止顺序错误')
        require((fs, fe) == (cs, ce), '业务与聊天统计周不一致')
        require(fc <= cc, '业务数据截止不得晚于聊天报告资料截止')
    except TypeError:
        raise ValueError('业务指标：时间须采用一致的时区口径') from None
    require(finance_window['time_basis'] == chat_window['time_basis'], '业务与聊天时间口径不一致')


def _pace(value, actual, target, cutoff, path):
    """Compare a supplied business schedule at exactly the actual-data cutoff."""
    if value is None:
        return None
    require(isinstance(value, dict) and set(value) == {'expected_net_revenue', 'as_of', 'source'},
            path + '须为expected_net_revenue/as_of/source；不自动平均分配目标')
    expected = amount(value['expected_net_revenue'], path + '.expected_net_revenue', nonnegative=True)
    as_of = text(value['as_of'], path + '.as_of')
    try:
        require(datetime.fromisoformat(as_of) == datetime.fromisoformat(cutoff),
                path + '.as_of必须与对应实际营收截止完全一致')
    except (TypeError, ValueError) as exc:
        raise ValueError('业务指标：' + path + '.as_of须与实际截止采用同一ISO时间口径') from exc
    gap = actual - expected
    return {'expected_net_revenue': number(expected), 'as_of': as_of,
            'source': text(value['source'], path + '.source'), 'actual_net_revenue': number(actual),
            'gap': number(gap), 'status': 'ahead' if gap > 0 else 'behind' if gap < 0 else 'on_track',
            'expected_attainment': number(expected / target) if target is not None else None}


def _metrics(row):
    purchases = row['first_formal_purchases']
    order_count = row['first_formal_order_count']
    order_total = row['first_formal_order_total']
    if purchases == 0:
        average, status = None, 'no_first_formal_purchases'
    elif order_count is None:
        average, status = None, 'missing_order_amounts'
    elif order_count != purchases:
        average, status = None, 'partial_order_coverage'
    else:
        average, status = order_total / purchases, 'complete'
    return {
        'net_revenue': number(row['net_revenue']),
        'target': number(row['target']),
        'target_attainment': number(row['net_revenue'] / row['target']) if row['target'] is not None else None,
        'effective_leads': count(row['effective_leads'], '合计有效流量'),
        'first_formal_purchases': count(purchases, '合计首次正式购买人数'),
        'effective_conversion_rate': number(Decimal(purchases) / row['effective_leads']) if row['effective_leads'] else None,
        'first_formal_order_total': number(order_total),
        'first_formal_order_count': count(order_count, '首单覆盖人数', nullable=True),
        'first_formal_order_average_rmb': number(average),
        'average_order_status': status,
        'pace': copy.deepcopy(row.get('pace')),
    }


def _monthly(value, sales_ids, chat_window, business_month, target_period=None):
    """Use an explicit business-system month total; never extrapolate a week."""
    if value is None:
        return None
    required = {'business_month', 'period', 'sales_ids', 'net_revenue', 'target', 'source'}
    require(isinstance(value, dict) and required <= set(value) <= required | {'pace'},
            'monthly须包含经营月、完整期间、顾问范围、净营收、目标及来源；未知目标显式null')
    month = value['business_month']
    require(isinstance(month, str) and re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', month)
            and not month.startswith('0000'), 'monthly.business_month须为明确的YYYY-MM')
    require(business_month is None or month == business_month, '月度与周度显式经营月标签不一致')
    ids = value['sales_ids']
    require(isinstance(ids, list) and ids, 'monthly.sales_ids须为顾问ID数组')
    for sid in ids:
        text(sid, 'monthly.sales_ids')
    require(len(ids) == len(set(ids)) and set(ids) == sales_ids,
            'monthly顾问集合须与报告范围完全一致且不得重复')
    period = value['period']
    require(isinstance(period, dict) and set(period) == {'start', 'end', 'cutoff', 'time_basis'},
            'monthly.period须明确完整经营月起止、累计截止与时间口径')
    text(period['time_basis'], 'monthly.period.time_basis')
    require(period['time_basis'] == chat_window['time_basis'], '月度与聊天报告时间口径不一致')
    parsed = []
    for key in ('start', 'end', 'cutoff'):
        text(period[key], 'monthly.period.' + key)
        try:
            parsed.append(datetime.fromisoformat(period[key]))
        except ValueError:
            raise ValueError('业务指标：monthly.period.' + key + '须为ISO时间') from None
    start, end, cutoff = parsed
    week_start = datetime.fromisoformat((target_period or {}).get('start', chat_window['week_start']))
    week_end = datetime.fromisoformat((target_period or {}).get('end', chat_window['week_end']))
    chat_cutoff = datetime.fromisoformat(chat_window['cutoff'])
    try:
        require(start <= week_start <= week_end <= end, '完整经营月期间须包含当前统计周')
        require(week_start <= cutoff <= chat_cutoff,
                '月累计截止须不早于当期周开始，且不得晚于报告资料截止')
    except TypeError:
        raise ValueError('业务指标：月度与报告时间须采用一致的时区口径') from None
    revenue = amount(value['net_revenue'], 'monthly.net_revenue')
    target = amount(value['target'], 'monthly.target', nullable=True, positive=True)
    return {
        'business_month': month, 'period': copy.deepcopy(period), 'sales_ids': sorted(sales_ids),
        'net_revenue': number(revenue), 'target': number(target),
        'target_attainment': number(revenue / target) if target is not None else None,
        'source': text(value['source'], 'monthly.source'),
        'pace': _pace(value.get('pace'), revenue, target, period['cutoff'], 'monthly.pace'),
    }


def build(payload, sales_ids, reporting_window, target_period=None):
    """Validate supplied business values and return scoped advisor/team metrics.

    A count smaller than formal purchases is partial coverage, not an average.
    No payload is a valid unavailable state. Invalid payloads raise ValueError.
    """
    target_period = validate_target_period(target_period, reporting_window)
    if payload is None:
        return {'schema_version': RESULT_SCHEMA, 'available': False,
                'reason': '未提供业务数据', 'advisors': [], 'team': None, 'targets': {}, 'monthly': None,
                'target_period': copy.deepcopy(target_period)}
    require(isinstance(payload, dict), '输入须为对象或null')
    require(payload.get('schema_version') == SCHEMA, '不支持的输入版本')
    require(payload.get('currency') == 'CNY', '本合同只接受明确人民币CNY，不自动换汇')
    require(payload.get('definitions') == DEFINITIONS, '必须明确净营收、当期有效转化及首次正式订单口径')
    _window(payload.get('reporting_window'), reporting_window)
    supplied_target = validate_target_period(payload.get('target_period'), payload['reporting_window'])
    require(supplied_target == target_period,
            '业务完整考核周须与成员结果一致；周中累计必须显式提供同一target_period')
    text(payload.get('scope_note'), 'scope_note')
    month = payload.get('business_month')
    if month is not None:
        require(isinstance(month, str) and re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])', month)
                and not month.startswith('0000'), 'business_month须为明确的YYYY-MM，不自动推算跨月归属')
    targets = payload.get('targets')
    require(isinstance(targets, dict) and set(targets) == {'effective_conversion', 'first_formal_order_rmb'}, '需要显式targets配置，未知为null，不使用机构默认目标')
    conversion_target = amount(targets.get('effective_conversion'), 'targets.effective_conversion', nullable=True, nonnegative=True)
    require(conversion_target is None or conversion_target <= 1, '转化目标须为0至1的小数')
    order_target = amount(targets.get('first_formal_order_rmb'), 'targets.first_formal_order_rmb', nullable=True, positive=True)
    require(isinstance(sales_ids, (list, tuple, set)) and bool(sales_ids), '需要报告顾问范围')
    for sid in sales_ids:
        text(sid, 'sales_ids')
    require(len(sales_ids) == len(set(sales_ids)), '报告顾问编号重复')
    expected = set(sales_ids)
    advisors = payload.get('advisors')
    require(isinstance(advisors, list), 'advisors须为数组')
    rows, seen = [], set()
    for item in advisors:
        require(isinstance(item, dict), '每位顾问指标须为对象')
        sid = text(item.get('sales_id'), 'advisor.sales_id')
        require(sid not in seen, '业务顾问编号重复：' + sid)
        seen.add(sid)
        row = {
            'sales_id': sid,
            'net_revenue': amount(item.get('net_revenue'), sid + '.net_revenue'),
            'target': amount(item.get('target'), sid + '.target', nullable=True, positive=True),
            'effective_leads': count(item.get('effective_leads'), sid + '.effective_leads'),
            'first_formal_purchases': count(item.get('first_formal_purchases'), sid + '.first_formal_purchases'),
            'first_formal_order_total': amount(item.get('first_formal_order_total'), sid + '.first_formal_order_total', nullable=True, nonnegative=True),
            'first_formal_order_count': count(item.get('first_formal_order_count'), sid + '.first_formal_order_count', nullable=True),
            'source': text(item.get('source'), sid + '.source'),
        }
        row['pace'] = _pace(item.get('pace'), row['net_revenue'], row['target'],
                            payload['reporting_window']['cutoff'], sid + '.pace')
        require(('target' in item and 'first_formal_order_total' in item and 'first_formal_order_count' in item),
                sid + '未知目标或首单数据必须显式null')
        total, coverage = row['first_formal_order_total'], row['first_formal_order_count']
        require((total is None) == (coverage is None), sid + '首单金额与覆盖人数必须同时提供或同时null')
        if coverage is not None:
            require(coverage <= row['first_formal_purchases'], sid + '首单覆盖人数不能超过首次正式购买人数')
            require(coverage != 0 or total == 0, sid + '首单人数为0时金额必须为0')
        rows.append(row)
    require(seen == expected, '业务顾问集合须与报告范围完全一致，不能遗漏或混入其他团队')
    rows.sort(key=lambda item: item['sales_id'])
    total = {
        'net_revenue': sum((row['net_revenue'] for row in rows), Decimal(0)),
        'target': sum((row['target'] for row in rows), Decimal(0)) if all(row['target'] is not None for row in rows) else None,
        'effective_leads': sum(row['effective_leads'] for row in rows),
        'first_formal_purchases': sum(row['first_formal_purchases'] for row in rows),
        'first_formal_order_total': sum((row['first_formal_order_total'] for row in rows), Decimal(0)) if all(row['first_formal_order_total'] is not None for row in rows) else None,
        'first_formal_order_count': sum(row['first_formal_order_count'] for row in rows) if all(row['first_formal_order_count'] is not None for row in rows) else None,
    }
    total['pace'] = None
    if all(row['pace'] is not None for row in rows):
        expected_total = sum((Decimal(str(row['pace']['expected_net_revenue'])) for row in rows), Decimal(0))
        total['pace'] = _pace({'expected_net_revenue': expected_total,
                               'as_of': payload['reporting_window']['cutoff'],
                               'source': '同一截至时点的全体顾问进度基准合计'},
                              total['net_revenue'], total['target'], payload['reporting_window']['cutoff'], 'team.pace')
        total['pace']['sources'] = [{'sales_id': row['sales_id'], 'source': row['pace']['source']} for row in rows]
    return {
        'schema_version': RESULT_SCHEMA, 'available': True, 'currency': 'CNY',
        'reporting_window': copy.deepcopy(payload['reporting_window']),
        'target_period': copy.deepcopy(target_period),
        'chat_cutoff': reporting_window['cutoff'], 'business_month': month,
        'scope_note': payload['scope_note'], 'definitions': copy.deepcopy(DEFINITIONS),
        'targets': {'effective_conversion': number(conversion_target), 'first_formal_order_rmb': number(order_target)},
        'advisors': [dict(sales_id=row['sales_id'], source=row['source'], **_metrics(row)) for row in rows],
        'team': dict(sales_ids=sorted(expected), sources=[row['source'] for row in rows], **_metrics(total)),
        'monthly': _monthly(payload.get('monthly'), expected, reporting_window, month, target_period),
    }
