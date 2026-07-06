"""
反洗钱风险自评估引擎（公司层面）
- 四维评估模型：客户风险 · 产品/业务风险 · 渠道风险 · 地域风险
- 数据库驱动：评估指标从 assessment_item 表读取，不再硬编码
- 支持多套行业模板（银行/基金/保险）
"""
from datetime import datetime
from typing import Optional

from backend.database import get_connection


class AMLEngine:
    """公司层面反洗钱风险自评估（数据库驱动）"""

    def __init__(self, preset_id: str = "preset_securities"):
        self.preset_id = preset_id
        self.conn = get_connection()

    # ═══════════════════════════════════════════════
    # 主评估流程
    # ═══════════════════════════════════════════════

    def assess(self) -> dict:
        """执行全公司反洗钱风险自评估"""
        cursor = self.conn.cursor()

        # 获取基础数据
        customers = self._fetch_all(cursor, "customer")
        accounts = self._fetch_all(cursor, "account")
        transactions = self._fetch_all(cursor, "trans_record")
        products = self._fetch_all(cursor, "product")

        # 关联产品信息到账户（后续可能需要）
        prod_map = {p["product_id"]: p for p in products}
        for a in accounts:
            a["_product"] = prod_map.get(a.get("product_id"), {})

        # 构建数据上下文，供 data_source 执行时使用
        data_ctx = {
            "customers": customers,
            "accounts": accounts,
            "transactions": transactions,
            "products": products,
            "cursor": cursor,
            "total_customers": len(customers),
            "total_accounts": len(accounts),
            "total_transactions": len(transactions),
            "total_products": len(products),
        }

        # 从数据库加载评估指标
        dim_items = {
            "customer": self._load_items("customer"),
            "product": self._load_items("product"),
            "channel": self._load_items("channel"),
            "geography": self._load_items("geography"),
        }

        # 四维评估
        dim_names = {
            "customer": "客户风险",
            "product": "产品/业务风险",
            "channel": "渠道风险",
            "geography": "地域风险",
        }
        dimension_results = {}
        all_recommendations = []

        for dim_key in ["customer", "product", "channel", "geography"]:
            items = dim_items[dim_key]
            result = self._assess_dimension(dim_names[dim_key], items, data_ctx)
            dimension_results[dim_key] = result
            all_recommendations.extend(result.get("recommendations", []))

        # 评估完成后再关闭连接
        self.conn.close()

        # 加权总分（四维权重可配置，默认均等）
        dim_weights = {
            "customer": 0.30, "product": 0.25,
            "channel": 0.25, "geography": 0.20,
        }
        overall = round(sum(
            dimension_results[k]["score"] * dim_weights[k]
            for k in ["customer", "product", "channel", "geography"]
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

        return {
            "status": "ok",
            "assessment_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "preset_id": self.preset_id,
            "data_summary": {
                "customers": data_ctx["total_customers"],
                "accounts": data_ctx["total_accounts"],
                "transactions": data_ctx["total_transactions"],
                "products": data_ctx["total_products"],
            },
            "overall_score": overall,
            "risk_level": level,
            "risk_level_name": level_name,
            "dimensions": dimension_results,
            "recommendations": all_recommendations,
        }

    # ═══════════════════════════════════════════════
    # 统一维度评估
    # ═══════════════════════════════════════════════

    def _assess_dimension(self, name: str, items: list[dict],
                          ctx: dict) -> dict:
        """统一评估一个维度下的所有指标"""
        results = []

        for item in items:
            # 获取实际数据
            actual_value = self._execute_data_source(item, ctx)
            total = self._get_total_for_item(item, ctx)

            if item["category"] == "framework":
                # 框架型：直接使用预设风险等级
                risk = item.get("default_risk", "中")
                detail = item.get("description", "需进一步核查")
                remark = item.get("description", "")
            else:
                # 数据驱动型：根据阈值判断
                risk = self._calc_risk(actual_value, total, item)
                detail = self._build_detail(actual_value, total, item, ctx)
                remark = item.get("description", "")

            results.append({
                "name": item["name"],
                "risk": risk,
                "detail": detail,
                "remark": remark,
                "item_key": item["item_key"],
                "category": item["category"],
                "raw_value": actual_value,
            })

        # 生成整改建议
        recommendations = self._build_recommendations(name, results)

        return self._calc_dim_score(name, results, recommendations)

    # ═══════════════════════════════════════════════
    # 数据源执行
    # ═══════════════════════════════════════════════

    def _execute_data_source(self, item: dict, ctx: dict) -> float:
        """执行指标的 data_source，返回数值结果"""
        ds = item.get("data_source") or ""

        if not ds:
            return 0

        if ds.startswith("func:"):
            # 函数型：调用对应内部方法
            func_name = ds[5:]  # 去掉 "func:" 前缀
            method = getattr(self, f"_calc_{func_name}", None)
            if method:
                return method(ctx)
            print(f"[WARN] 未找到函数: _calc_{func_name}")
            return 0

        if ds.upper().startswith("SELECT"):
            # SQL型：执行查询
            try:
                cursor = ctx["cursor"]
                cursor.execute(ds)
                row = cursor.fetchone()
                if row:
                    # 兼容两种返回: {"cnt": N} 或 {"COUNT(*)": N}
                    val = row["cnt"] if "cnt" in row.keys() else row[0]
                    return float(val) if val is not None else 0
            except Exception as e:
                print(f"[WARN] SQL执行失败 [{item.get('item_key')}]: {e}")
                return 0

        return 0

    def _get_total_for_item(self, item: dict, ctx: dict) -> int:
        """获取指标的分母（用于计算比例）"""
        dim = item.get("dimension", "")
        data_source = item.get("data_source") or ""

        if dim == "customer" or "customer" in data_source.lower():
            return max(ctx["total_customers"], 1)
        elif dim == "product" or "product" in data_source.lower():
            # 部分产品指标以product为分母，渠道指标以transaction为分母
            if "product" in data_source.lower():
                return max(ctx["total_products"], 1)
            return max(ctx["total_transactions"], 1)
        elif dim == "channel":
            return max(ctx["total_transactions"], 1)
        elif dim == "geography":
            if "customer" in data_source.lower():
                return max(ctx["total_customers"], 1)
            return max(ctx["total_transactions"], 1)

        # 默认根据 item_key 推断
        key = item.get("item_key", "")
        if "cust" in key:
            return max(ctx["total_customers"], 1)
        elif "prod" in key:
            return max(ctx["total_products"], 1)
        else:
            return max(ctx["total_transactions"], 1)

    def _calc_risk(self, value: float, total: int,
                   item: dict) -> str:
        """根据阈值计算风险等级"""
        th_high = item.get("threshold_high")
        th_mid = item.get("threshold_mid")

        if th_high is None and th_mid is None:
            return "中"

        ratio = value / max(total, 1)

        # 阈值含义：threshold_high > 1 表示绝对数值阈值（如产品类型数），
        # 否则表示比例阈值
        if th_high is not None and th_high > 1:
            # 绝对数值型阈值
            if value >= th_high:
                return "高"
            elif th_mid and value >= th_mid:
                return "中"
            else:
                return "低"
        else:
            # 比例型阈值
            if th_high and ratio > th_high:
                return "高"
            elif th_mid and ratio > th_mid:
                return "中"
            else:
                return "低"

    def _build_detail(self, value: float, total: int,
                      item: dict, ctx: dict) -> str:
        """根据指标生成人类可读的数据详情文本"""
        key = item.get("item_key", "")
        th_high = item.get("threshold_high") or 0

        # 绝对数值型
        if th_high > 1:
            return f"共 {int(value)}"

        # 比例型
        pct = round(value / max(total, 1) * 100, 1)
        return f"共 {int(value)} 条 ({pct}%)"

    # ═══════════════════════════════════════════════
    # 函数型数据源（func:xxx 对应 _calc_xxx）
    # ═══════════════════════════════════════════════

    def _calc_top5_concentration(self, ctx: dict) -> float:
        """前5名客户交易金额占比"""
        transactions = ctx["transactions"]
        from collections import defaultdict
        cust_amounts = defaultdict(float)
        for t in transactions:
            cust_amounts[t.get("customer_id", "")] += abs(t.get("amount") or 0)
        top5 = sum(sorted(cust_amounts.values(), reverse=True)[:5])
        total_amount = sum(cust_amounts.values())
        return round(top5 / max(total_amount, 1), 4)

    def _calc_avg_accounts_per_customer(self, ctx: dict) -> float:
        """人均持账户数"""
        accounts = ctx["accounts"]
        cust_ids = set(a.get("customer_id") for a in accounts if a.get("customer_id"))
        return round(len(accounts) / max(len(cust_ids), 1), 1)

    def _calc_channel_amount_cross(self, ctx: dict) -> float:
        """非面对面渠道 × 大额交易交叉占比"""
        transactions = ctx["transactions"]
        non_face_channels = {"手机银行", "网银", "代销", "ATM"}
        cross = [
            t for t in transactions
            if t.get("channel") in non_face_channels
            and abs(t.get("amount") or 0) > 1000000
        ]
        return len(cross)

    def _calc_province_diversity(self, ctx: dict) -> int:
        """客户覆盖的省级行政区数量"""
        provinces = set()
        all_provinces = [
            "北京", "上海", "广东", "深圳", "四川", "湖北", "浙江", "江苏",
            "福建", "山东", "河北", "河南", "湖南", "陕西", "云南", "贵州",
            "广西", "辽宁", "吉林", "黑龙江", "重庆", "天津", "海南", "甘肃",
            "宁夏", "青海", "西藏", "新疆", "内蒙古", "安徽", "江西", "山西",
        ]
        for c in ctx["customers"]:
            addr = c.get("address", "") or ""
            for prov in all_provinces:
                if prov in addr:
                    provinces.add(prov)
        return len(provinces)

    def _calc_cross_region_ratio(self, ctx: dict) -> float:
        """
        异地交易占比：客户所在地与交易对手方所在地不一致的比例
        简化版：统计交易对手方信息中包含非本地省份的交易占比
        """
        transactions = ctx["transactions"]
        if not transactions:
            return 0

        # 构建客户省份映射
        all_provinces = [
            "北京", "上海", "广东", "深圳", "四川", "湖北", "浙江", "江苏",
            "福建", "山东", "河北", "河南", "湖南", "陕西", "云南", "贵州",
            "广西", "辽宁", "吉林", "黑龙江", "重庆", "天津", "海南", "甘肃",
            "宁夏", "青海", "西藏", "新疆", "内蒙古", "安徽", "江西", "山西",
        ]
        cust_province = {}
        for c in ctx["customers"]:
            addr = c.get("address", "") or ""
            found = None
            for prov in all_provinces:
                if prov in addr:
                    found = prov
                    break
            cust_province[c.get("customer_id")] = found

        cross_count = 0
        for t in transactions:
            cp_info = t.get("counterparty_info", "") or ""
            cust_prov = cust_province.get(t.get("customer_id"))
            if cust_prov and cp_info:
                # 如果对手方信息中包含其他省份，视为异地交易
                for prov in all_provinces:
                    if prov != cust_prov and prov in cp_info:
                        cross_count += 1
                        break

        return round(cross_count / max(len(transactions), 1), 4)

    def _calc_surrender_ratio(self, ctx: dict) -> float:
        """
        退保交易占比（保险模板专用）
        统计交易类型为退保或退费的占比
        """
        transactions = ctx["transactions"]
        if not transactions:
            return 0
        surrender = [
            t for t in transactions
            if t.get("transaction_type", "") in ("退保", "退费", "赎回")
        ]
        return len(surrender)

    # ═══════════════════════════════════════════════
    # 数据库加载
    # ═══════════════════════════════════════════════

    def _load_items(self, dimension: str) -> list[dict]:
        """从数据库加载指定维度的启用的评估指标"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM assessment_item
            WHERE preset_id = ? AND dimension = ? AND enabled = 1
            ORDER BY sort_order
        """, (self.preset_id, dimension))
        return [dict(r) for r in cursor.fetchall()]

    # ═══════════════════════════════════════════════
    # 评分与建议
    # ═══════════════════════════════════════════════

    def _calc_dim_score(self, name: str, items: list,
                        recommendations: list) -> dict:
        """根据评估项计算维度得分"""
        risk_vals = {"高": 85, "中": 50, "低": 15}
        scores = [risk_vals.get(i["risk"], 25) for i in items]
        raw = round(sum(scores) / len(scores), 1) if scores else 50

        high_cnt = sum(1 for i in items if i["risk"] == "高")
        mid_cnt = sum(1 for i in items if i["risk"] == "中")
        low_cnt = sum(1 for i in items if i["risk"] == "低")

        return {
            "name": name,
            "score": raw,
            "items": items,
            "summary": f"评估{len(items)}项: 高风险{high_cnt}项, "
                       f"中风险{mid_cnt}项, 低风险{low_cnt}项",
            "recommendations": recommendations,
        }

    def _build_recommendations(self, dim_name: str,
                               results: list) -> list:
        """根据评估结果自动生成整改建议"""
        recs = []
        high_items = [r for r in results if r["risk"] == "高"]
        mid_items = [r for r in results if r["risk"] == "中"]

        for item in high_items:
            recs.append(f"[{dim_name}] {item['name']}风险为高，"
                        f"建议优先整改。{item['remark']}")

        for item in mid_items[:3]:  # 中风险最多3条建议
            recs.append(f"[{dim_name}] {item['name']}风险为中，"
                        f"建议持续关注。{item['remark']}")

        if not recs:
            recs.append(f"[{dim_name}] 本维度未发现高风险项，建议保持现状并持续监控。")

        return recs

    # ═══════════════════════════════════════════════
    # 数据库辅助
    # ═══════════════════════════════════════════════

    def _fetch_all(self, cursor, table: str) -> list[dict]:
        """获取表中所有记录"""
        cursor.execute(f"SELECT * FROM {table}")
        return [dict(r) for r in cursor.fetchall()]


# ═══════════════════════════════════════════════
# 兼容旧接口
# ═══════════════════════════════════════════════

def assess_company(preset_id: str = "preset_securities") -> dict:
    """便捷函数：执行公司层面反洗钱风险自评估"""
    engine = AMLEngine(preset_id=preset_id)
    return engine.assess()
