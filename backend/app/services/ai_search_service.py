"""AI 自然语言检索编排：自然语言 -> 解析 -> 检索 -> AI 解读。"""

import json

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.data_access_service import DataAccessService
from app.services.llm_client import chat, chat_json
from app.services.search_service import SearchService


class AISearchService:
    def __init__(self, db: Session):
        self.db = db

    def ask(self, current_user: User, dataset_id: int, index_id: int, question: str) -> dict:
        data_access = DataAccessService(self.db)
        field_values = data_access.get_field_values(dataset_id)

        parsed = self._parse_question(question, field_values)
        payload = self._build_search_payload(data_access, dataset_id, index_id, parsed)

        search_result = SearchService(self.db).search(current_user, payload)
        results = search_result.get("results", [])

        cell_ids = [item["cell_id"] for item in results]
        stats = data_access.aggregate_metadata(dataset_id, cell_ids)

        answer = self._generate_answer(question, parsed, stats)

        return {
            "question": question,
            "parsed_query": parsed,
            "answer": answer,
            "stats": stats,
            "query_id": search_result.get("query_id"),
            "latency_ms": search_result.get("latency_ms"),
            "results": results,
        }

    # ---------------- 第一步：自然语言 -> 结构化查询 ----------------
    def _parse_question(self, question: str, field_values: dict) -> dict:
        system_prompt = (
            "你是单细胞数据检索助手。请把用户的自然语言问题解析成 JSON 检索条件。"
            "只能输出 JSON，不要解释。字段说明：\n"
            "- query_type: 固定为 'cell_id'\n"
            "- cell_id: 如果用户明确提到某个细胞ID则填写，否则为 null\n"
            "- filters: 对象，可包含 cell_type / organ / disease / AgeGroup / sex，"
            "每个值必须从下面给定的可选值里精确选择，选不到就不要这个键\n"
            "- top_k: 整数，用户没指定就用 10\n"
            f"可选 cell_type: {json.dumps(field_values.get('cell_type', []), ensure_ascii=False)}\n"
            f"可选 organ: {json.dumps(field_values.get('organ', []), ensure_ascii=False)}\n"
            f"可选 disease: {json.dumps(field_values.get('disease', []), ensure_ascii=False)}\n"
            f"可选 AgeGroup: {json.dumps(field_values.get('AgeGroup', []), ensure_ascii=False)}\n"
            f"可选 sex: {json.dumps(field_values.get('sex', []), ensure_ascii=False)}\n"
            "输出示例: {\"query_type\":\"cell_id\",\"cell_id\":null,"
            "\"filters\":{\"cell_type\":\"Kupffer cell\",\"disease\":\"normal\"},\"top_k\":10}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        parsed = chat_json(messages)

        # 基础清洗与兜底
        parsed.setdefault("query_type", "cell_id")
        parsed.setdefault("filters", {})
        parsed.setdefault("top_k", 10)
        if not isinstance(parsed.get("filters"), dict):
            parsed["filters"] = {}
        try:
            parsed["top_k"] = max(1, min(int(parsed["top_k"]), 100))
        except (TypeError, ValueError):
            parsed["top_k"] = 10
        return parsed

    MAIN_FIELDS = ("cell_type", "organ", "sample_id")
    EXT_FIELDS = ("disease", "AgeGroup", "sex")

    def _build_search_payload(
        self,
        data_access: DataAccessService,
        dataset_id: int,
        index_id: int,
        parsed: dict,
    ) -> dict:
        raw_filters = {
            k: v
            for k, v in (parsed.get("filters") or {}).items()
            if k in (self.MAIN_FIELDS + self.EXT_FIELDS) and v not in (None, "", [])
        }
        top_k = parsed.get("top_k", 10)
        cell_id = parsed.get("cell_id")

        # 用户明确指定了 cell_id：直接用它做查询锚点
        if cell_id:
            return {
                "dataset_id": dataset_id,
                "index_id": index_id,
                "query_type": "cell_id",
                "cell_id": cell_id,
                "top_k": top_k,
                "mode": "ann",
                "filters": self._search_filters(raw_filters),
                "_record_task": True,
            }

        # 否则用符合过滤条件的细胞群的“类中心向量”作为锚点，更稳定有代表性
        matched_ids = data_access.filter_cell_ids(dataset_id, raw_filters)
        if not matched_ids:
            # 没有任何细胞匹配过滤条件，退回全数据集
            matched_ids = data_access.filter_cell_ids(dataset_id, {})
        centroid = data_access.get_centroid_vector(dataset_id, matched_ids)

        return {
            "dataset_id": dataset_id,
            "index_id": index_id,
            "query_type": "vector",
            "vector": centroid.tolist(),
            "top_k": top_k,
            "mode": "ann",
            "filters": self._search_filters(raw_filters),
            "_record_task": True,
        }

    # 把解析出的 filters 转成检索引擎能识别的形式：
    # 主字段保持原样，扩展字段加 obs_ext. 前缀（检索引擎支持 obs_ext.xxx）
    def _search_filters(self, raw_filters: dict) -> dict:
        result = {}
        for key, value in raw_filters.items():
            if key in self.MAIN_FIELDS:
                result[key] = value
            else:
                result[f"obs_ext.{key}"] = value
        return result

    # ---------------- 第三步：基于真实统计生成解读 ----------------
    def _generate_answer(self, question: str, parsed: dict, stats: dict) -> str:
        system_prompt = (
            "你是单细胞数据分析助手。请根据下面的真实检索统计，用简洁中文解读结果。"
            "只能基于给定数据陈述，不要编造未提供的信息。控制在 3-5 句话。"
        )
        user_content = (
            f"用户问题：{question}\n"
            f"解析出的检索条件：{json.dumps(parsed, ensure_ascii=False)}\n"
            f"检索结果统计：{json.dumps(stats, ensure_ascii=False)}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        return chat(messages, temperature=0.3, max_tokens=512)
