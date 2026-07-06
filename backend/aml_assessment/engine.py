"""
反洗钱风险自评估引擎（公司层面）
- 四维评估模型：客户风险 · 产品/业务风险 · 渠道风险 · 地域风险
- 自动分析数据库真实数据 + 框架性评估项
"""
from datetime import datetime
from typing import Optional

from backend.database import get_connection


# ── 高风险国家/地区 ──
HIGH_RISK_COUNTRIES = [
    "伊朗", "朝鲜", "缅甸", "叙利亚", "也门", "阿富汗", "伊拉克",
    "刚果", "南苏丹", "苏丹", "索马里", "利比亚", "马里",
    "巴哈马", "巴巴多斯", "保加利亚", "布基纳法索", "喀麦隆", "克罗地亚",
    "直布罗陀", "海地", "牙买加", "莫桑比克", "尼日利亚", "菲律宾",
    "塞内加尔", "坦桑尼亚", "土耳其", "乌干达", "阿联酋", "越南",
]

HIGH_RISK_OCCUPATIONS = ["个体工商户", "自由职业者", "企业高管"]
MEDIUM_RISK_OCCUPATIONS = ["律师", "会计师", "工程师", "企业员工", "公务员"]


class AMLEngine:
    """公司层面反洗钱风险自评估"""

    def __init__(self):
        self.conn = get_connection()

    # ── 主评估流程 ──

    def assess(self) -> dict:
        """执行全公司反洗钱风险自评估"""
        cursor = self.conn.cursor()

        # 获取基础数据
        customers = self._fetch_all(cursor, "customer")
        accounts = self._fetch_all(cursor, "account")
        transactions = self._fetch_all(cursor, "trans_record")
        products = self._fetch_all(cursor, "product")

        # 关联产品信息到账户
        prod_map = {p["product_id"]: p for p in products}
        for a in accounts:
            a["_product"] = prod_map.get(a.get("product_id"), {})

        self.conn.close()

        # 四维评估
        customer_result = self._assess_customer(customers, accounts)
        product_result = self._assess_product(accounts, products)
        channel_result = self._assess_channel(transactions)
        geography_result = self._assess_geography(customers, transactions)

        # 加权总分
        weights = {"customer": 0.30, "product": 0.25, "channel": 0.25, "geography": 0.20}
        overall = round(sum(
            r["score"] * weights[k]
            for k, r in [("customer", customer_result), ("product", product_result),
                         ("channel", channel_result), ("geography", geography_result)]
        ), 1)

        # 风险等级
        if overall <= 30:
            level, level_name = "低", "低风险"
        elif overall <= 60:
            level, level_name = "中", "中风险"
        elif overall <= 80:
            level, level_name = "高", "高风险"
        else:
            level, level_name = "最高", "最高风险"

        # 汇总整改建议
        all_recommendations = []
        for dim_result in [customer_result, product_result, channel_result, geography_result]:
            all_recommendations.extend(dim_result.get("recommendations", []))

        return {
            "status": "ok",
            "assessment_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_summary": {
                "customers": len(customers),
                "accounts": len(accounts),
                "transactions": len(transactions),
                "products": len(products),
            },
            "overall_score": overall,
            "risk_level": level,
            "risk_level_name": level_name,
            "dimensions": {
                "customer": customer_result,
                "product": product_result,
                "channel": channel_result,
                "geography": geography_result,
            },
            "recommendations": all_recommendations,
        }

    # ── 一、客户风险评估 ──

    def _assess_customer(self, customers: list, accounts: list) -> dict:
        items = []
        total = max(len(customers), 1)

        # 1.1 高风险职业客户
        high_occ = [c for c in customers if c.get("occupation") in HIGH_RISK_OCCUPATIONS]
        risk = "高" if len(high_occ) / total > 0.3 else "中" if len(high_occ) / total > 0.1 else "低"
        items.append({
            "name": "高风险职业客户",
            "risk": risk,
            "detail": f"共 {len(high_occ)} 人 ({round(len(high_occ)/total*100, 1)}%)",
            "remark": f"包括个体工商户、自由职业者、企业高管等",
        })

        # 1.2 客户自身风险等级分布
        high_cl = sum(1 for c in customers if c.get("risk_level") == "高")
        mid_cl = sum(1 for c in customers if c.get("risk_level") == "中")
        risk = "高" if high_cl / total > 0.2 else "中" if high_cl / total > 0.05 else "低"
        items.append({
            "name": "客户风险等级分布",
            "risk": risk,
            "detail": f"高: {high_cl}人 | 中: {mid_cl}人 | 低: {total-high_cl-mid_cl}人",
            "remark": f"高/中风险客户占比 {round((high_cl+mid_cl)/total*100, 1)}%",
        })

        # 1.3 证件类型
        passport_cnt = sum(1 for c in customers if c.get("id_type") == "护照")
        risk = "中" if passport_cnt > 0 else "低"
        items.append({
            "name": "非居民客户（护照开户）",
            "risk": risk,
            "detail": f"共 {passport_cnt} 人" if passport_cnt else "无",
            "remark": "非居民身份需加强身份识别" if passport_cnt else "未发现非居民客户",
        })

        # 1.4 客户信息完整性
        incomplete = sum(1 for c in customers
                         if not c.get("id_number") or not c.get("phone") or not c.get("email"))
        risk = "高" if incomplete / total > 0.1 else "中" if incomplete > 0 else "低"
        items.append({
            "name": "客户九要素信息完整性",
            "risk": risk,
            "detail": f"信息缺失: {incomplete}人" if incomplete else "全部完整",
            "remark": "影响CDD有效执行" if incomplete else "KYC信息完备",
        })

        # 1.5 受益所有人穿透（框架性）
        items.append({
            "name": "受益所有人穿透识别",
            "risk": "中",
            "detail": "需进一步核查",
            "remark": "建议对高风险客户执行穿透识别至最终自然人",
        })

        return self._calc_dim_score("客户风险", items, [
            "对高风险职业客户及高/中风险等级客户执行强化尽职调查（EDD）",
            "完善客户九要素信息，降低信息缺失率",
            "对受益所有人结构复杂的客户进行穿透识别",
        ])

    # ── 二、产品/业务风险评估 ──

    def _assess_product(self, accounts: list, products: list) -> dict:
        items = []
        prod_count = max(len(products), 1)

        # 按产品类型归类
        type_dist = {}
        for p in products:
            ptype = p.get("product_type", "未知")
            type_dist[ptype] = type_dist.get(ptype, 0) + 1

        # 2.1 高风险产品
        high_risk_types = {"私募-股票多头", "私募-量化对冲", "专户-权益"}
        high_risk_prods = [p for p in products if p.get("product_type") in high_risk_types]
        risk = "高" if len(high_risk_prods) / prod_count > 0.2 else "中" if high_risk_prods else "低"
        items.append({
            "name": "高风险产品（私募/专户权益类）",
            "risk": risk,
            "detail": f"共 {len(high_risk_prods)} 只 ({round(len(high_risk_prods)/prod_count*100,1)}%)",
            "remark": f"包括私募股票多头、量化对冲、专户权益等",
        })

        # 2.2 产品类型分布
        type_list = [f"{k}:{v}只" for k, v in sorted(type_dist.items(), key=lambda x:-x[1])[:5]]
        items.append({
            "name": "产品类型分布",
            "risk": "中" if len(type_dist) > 5 else "低",
            "detail": " | ".join(type_list),
            "remark": "产品类型越多样，风险复杂度越高",
        })

        # 2.3 新产品上线评估
        items.append({
            "name": "新产品/新业务上线洗钱风险评估",
            "risk": "中",
            "detail": "需确认流程完整性",
            "remark": "建议建立新产品上线前洗钱风险评估流程并留痕",
        })

        # 2.4 关联账户数
        avg_accounts = len(accounts) / max(len(set(a.get("customer_id") for a in accounts)), 1)
        risk = "中" if avg_accounts > 2 else "低"
        items.append({
            "name": "人均持账户数",
            "risk": risk,
            "detail": f"平均 {round(avg_accounts, 1)} 个/人",
            "remark": "人均多账户可能被用于分层交易规避监测",
        })

        return self._calc_dim_score("产品/业务风险", items, [
            "对高风险产品（私募/专户）执行专项洗钱风险评估",
            "建立新产品上线前洗钱风险评估机制",
            "关注一人多户情况，排查是否存在规避监测行为",
        ])

    # ── 三、渠道风险评估 ──

    def _assess_channel(self, transactions: list) -> dict:
        items = []
        total = max(len(transactions), 1)

        # 渠道分布
        ch_dist = {}
        for t in transactions:
            ch = t.get("channel", "未知")
            ch_dist[ch] = ch_dist.get(ch, 0) + 1

        # 3.1 非面对面渠道
        non_face = sum(v for k, v in ch_dist.items() if k in ("手机银行", "网银", "代销", "ATM"))
        risk = "高" if non_face / total > 0.7 else "中" if non_face / total > 0.4 else "低"
        items.append({
            "name": "非面对面业务渠道占比",
            "risk": risk,
            "detail": f"{non_face}笔 ({round(non_face/total*100, 1)}%)",
            "remark": "非面对面渠道增加匿名风险",
        })

        # 3.2 渠道分布明细
        items.append({
            "name": "渠道分布",
            "risk": "中" if len(ch_dist) > 3 else "低",
            "detail": " | ".join(f"{k}:{round(v/total*100,1)}%" for k, v in sorted(ch_dist.items(), key=lambda x:-x[1])),
            "remark": "多渠道并存，需确保各渠道风控措施一致",
        })

        # 3.3 代销渠道
        daixiao = ch_dist.get("代销", 0)
        risk = "高" if daixiao / total > 0.15 else "中" if daixiao > 0 else "低"
        items.append({
            "name": "代销渠道风险",
            "risk": risk,
            "detail": f"{daixiao}笔 ({round(daixiao/total*100, 1)}%)" if daixiao else "无代销交易",
            "remark": "代销渠道客户识别依赖第三方，信息不对称风险高",
        })

        return self._calc_dim_score("渠道风险", items, [
            "加强非面对面渠道客户身份识别措施",
            "定期评估代销渠道反洗钱合规情况",
            "各渠道部署一致的交易监测规则",
        ])

    # ── 四、地域风险评估 ──

    def _assess_geography(self, customers: list, transactions: list) -> dict:
        items = []
        total_cust = max(len(customers), 1)
        total_txn = max(len(transactions), 1)

        # 4.1 高风险国家关联客户
        high_geo_cust = [c for c in customers if c.get("nationality") in HIGH_RISK_COUNTRIES]
        non_cn = [c for c in customers if c.get("nationality") != "中国"]
        risk = "高" if high_geo_cust else "中" if non_cn else "低"
        items.append({
            "name": "高风险/FATF名单国家关联客户",
            "risk": risk,
            "detail": f"高风险国家: {len(high_geo_cust)}人 | 非中国: {len(non_cn)}人",
            "remark": "高风险国籍客户需加强尽调" if high_geo_cust else "未发现FATF高风险国家关联",
        })

        # 4.2 跨境交易
        cross_txn = [t for t in transactions if t.get("currency", "CNY") != "CNY"]
        risk = "高" if len(cross_txn) / total_txn > 0.1 else "中" if cross_txn else "低"
        items.append({
            "name": "跨境交易占比",
            "risk": risk,
            "detail": f"{len(cross_txn)}笔 ({round(len(cross_txn)/total_txn*100,1)}%)" if cross_txn else "无跨境交易",
            "remark": "跨境交易须关注资金来源与去向" if cross_txn else "暂未发现跨境交易",
        })

        # 4.3 客户地域集中度
        provinces = set()
        for c in customers:
            addr = c.get("address", "")
            # 粗略提取地名
            for prov in ["北京", "上海", "广东", "深圳", "四川", "湖北", "浙江", "江苏", "福建", "山东",
                         "河北", "河南", "湖南", "陕西", "云南", "贵州", "广西", "辽宁", "吉林", "黑龙江",
                         "重庆", "天津", "海南", "甘肃", "宁夏", "青海", "西藏", "新疆", "内蒙古", "安徽",
                         "江西", "山西"]:
                if prov in (addr or ""):
                    provinces.add(prov)
        risk = "低" if len(provinces) > 5 else "中"
        items.append({
            "name": "客户地域分布",
            "risk": risk,
            "detail": f"覆盖约 {len(provinces)} 个地区" if provinces else "未能提取地域信息",
            "remark": "地域分布广泛，有利于风险分散" if len(provinces) > 5 else "地域较集中",
        })

        # 4.4 FATF声明核查
        items.append({
            "name": "FATF声明与制裁名单更新",
            "risk": "中",
            "detail": "需定期更新",
            "remark": "建议建立制裁名单定期更新与回溯机制",
        })

        return self._calc_dim_score("地域风险", items, [
            "对高风险国家关联客户执行EDD",
            "加强跨境交易资金流向监控",
            "建立制裁名单定期更新和回溯筛查机制",
        ])

    # ── 辅助方法 ──

    def _calc_dim_score(self, name: str, items: list, recommendations: list) -> dict:
        """根据评估项计算维度得分"""
        risk_vals = {"高": 85, "中": 50, "低": 15}
        scores = [risk_vals.get(i["risk"], 25) for i in items]
        raw = round(sum(scores) / len(scores), 1) if scores else 50

        # 统计风险分布
        high_cnt = sum(1 for i in items if i["risk"] == "高")
        mid_cnt = sum(1 for i in items if i["risk"] == "中")
        low_cnt = sum(1 for i in items if i["risk"] == "低")

        return {
            "name": name,
            "score": raw,
            "items": items,
            "summary": f"评估{len(items)}项: 高风险{high_cnt}项, 中风险{mid_cnt}项, 低风险{low_cnt}项",
            "recommendations": recommendations,
        }

    def _fetch_all(self, cursor, table: str) -> list[dict]:
        """获取表中所有记录"""
        cursor.execute(f"SELECT * FROM {table}")
        return [dict(r) for r in cursor.fetchall()]
