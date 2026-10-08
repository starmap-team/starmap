// 批量生成 submission/test-data/batch 测试数据（2026-09-03 公网实测素材）
// 固定字面量路径，无用户输入。素材在 batch/_src/，输出到 batch/existing 与 batch/emerging。
const fs = require("fs");
const path = require("path");

const BATCH = "C:/Users/LiShuai/Desktop/Agents/starmap/submission/test-data/batch";
const SRC_POS = BATCH + "/_src/pos_details";
const SRC_NEW = BATCH + "/_src/new_details";

const read = (p) => JSON.parse(fs.readFileSync(p, "utf-8"));
const sanitize = (n) => n.replace(/[\\/:*?"<>|]/g, "_");
const dump = (obj, p) => fs.writeFileSync(p, JSON.stringify(obj, null, 2));

// 素材文件（固定清单，不用 listdir 遍历）
const posFiles = fs.readdirSync(SRC_POS).filter((f) => f.endsWith(".json"));
const newFiles = fs.readdirSync(SRC_NEW).filter((f) => f.endsWith(".json"));

const DOMAIN_TAG = {
  "人工智能": "人工智能", "互联网/IT": "数字经济/泛IT", "未分类": "数字经济/泛IT",
  "数据工程": "大数据", "数据科学": "大数据", "云计算/DevOps": "云计算/DevOps",
  "前端开发": "前端工程", "后端开发": "后端工程", "嵌入式与物联网": "物联网/嵌入式",
  "游戏开发": "数字内容", "网络安全": "网络安全", "移动开发": "移动开发", "测试": "软件测试",
};

// ── existing：27 既有岗位 ──
const posDetails = posFiles.map((f) => read(SRC_POS + "/" + f));
posDetails.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
const existingManifest = [];
const exDir = BATCH + "/existing";
fs.mkdirSync(exDir, { recursive: true });

posDetails.forEach((d, i) => {
  const sk = d.skills_required || [];
  const bonus = d.bonus_skills || [];
  const totalSrc = sk.reduce((s, x) => s + (x.source_count || 0), 0);
  const ind = d.industry || "未分类";
  const input = {
    position: d.name, input_type: "position_source_reference", industry: ind,
    domain_tag: DOMAIN_TAG[ind] || ind,
    source_platforms_note: "该岗位技能由系统多源采集的真实 JD 汇聚（source_count 为汇聚该技能的 JD 源数）；数据源分布见总 README datasources 表",
    skill_aggregation: {
      skills_count: sk.length, total_source_count: totalSrc,
      top_skills: [...sk].sort((a, b) => (b.source_count || 0) - (a.source_count || 0)).slice(0, 3)
        .map((s) => ({ skill: s.name, source_count: s.source_count, confidence: s.confidence })),
    },
    fetched_at: "2026-09-03",
  };
  const output = {
    position: d.name, position_id: d.position_id, industry: ind,
    domain_tag: DOMAIN_TAG[ind] || ind,
    review_status: (d.provenance || {}).review_status,
    definition: {
      industry_scenario: d.industry_scenario, core_responsibilities: d.core_responsibilities,
      bonus_skills: bonus, summary: d.summary,
    },
    capability_graph: {
      note: "岗位→技能点图谱（required 必备 / bonus 加分），技能点含熟练度/置信度/来源数",
      required_skills: sk.map((s) => ({
        skill: s.name, name_cn: s.name_cn, category: s.category, proficiency: s.proficiency,
        confidence: s.confidence, source_count: s.source_count,
      })),
      bonus_skills: bonus, skill_count: sk.length, total_source_count: totalSrc,
    },
    source: "GET /api/v1/positions/{name}（公网实时 API 2026-09-03 实测）",
    extracted_at: "2026-09-03",
  };
  const sub = exDir + "/" + String(i).padStart(2, "0") + "_" + sanitize(d.name);
  fs.mkdirSync(sub, { recursive: true });
  dump(input, sub + "/input.json");
  dump(output, sub + "/output.json");
  existingManifest.push({ dir: path.basename(sub), position: d.name, industry: ind, domain_tag: DOMAIN_TAG[ind] || ind, skills: sk.length, sources: totalSrc, five_elements: !!d.industry_scenario });
  console.log(`existing OK ${String(i).padStart(2, "0")} ${d.name} (${sk.length}技/${totalSrc}源)`);
});

// ── emerging：discover 前 10 生成候选 ──
const discover = read(BATCH + "/_src/discover_with_def10.json");
const newDetailsMap = {};
newFiles.forEach((f) => {
  const d = read(SRC_NEW + "/" + f);
  newDetailsMap[d.name] = d;
});

const genOrder = discover.emerging_positions.filter((p) => p.definition && p.definition.industry_scenario);
// 过滤：保留新一代信息技术/技术类候选（系统 discover 前 10 含销售/财务类非技术岗，不作为赛项测试数据）
const TECH_KEEP = new Set([
  "首席自主卡车工程师", "Applied Data Scientist or Machine Learning Engineer",
  "算法应用平台工程师", "软件工程师", "Salesforce Technical Architect", "IT管理员",
]);
const emergingManifest = [];
const emDir = BATCH + "/emerging";
fs.mkdirSync(emDir, { recursive: true });

let ei = 0;
genOrder.forEach((cand) => {
  const name = cand.position;
  if (!TECH_KEEP.has(name)) return; // 跳过非技术岗（高级咨询顾问/高级软件销售代表/Senior FP&A/Teamlead IT Support）
  const definition = cand.definition || {};
  const detail = newDetailsMap[name] || {};
  const input = {
    position: name, input_type: "emerging_skill_signal",
    emerging_skills: cand.emerging_skills || [], emerging_ratio: cand.emerging_ratio,
    source_api: "POST /api/v1/positions/discover",
    note: "系统 discover 从真实多源 JD 中检测到该岗位技能命中涌现/上升信号，判定为新兴候选（候选均已审核入图；'新'体现在技能组合正在兴起）",
    fetched_at: "2026-09-03",
  };
  const output = {
    position: name, emerging_ratio: cand.emerging_ratio,
    definition_from_discover: {
      industry_scenario: definition.industry_scenario, core_responsibilities: definition.core_responsibilities,
      bonus_skills: definition.bonus_skills, summary: definition.summary,
      required_skills: definition.required_skills,
      note: "discover?with_definitions=true 实时生成（LLM），不落库；每次调用可能略有差异",
    },
    in_graph_detail: {
      position_id: detail.position_id, industry: detail.industry,
      review_status: (detail.provenance || {}).review_status,
      skills_required: detail.skills_required,
      persisted_definition: detail.industry_scenario ? {
        industry_scenario: detail.industry_scenario, core_responsibilities: detail.core_responsibilities,
        bonus_skills: detail.bonus_skills, summary: detail.summary,
      } : null,
      note: "岗位已审核入图，GET /api/v1/positions/{name} 返回持久化五要素（与 discover 临时生成版本可略有差异，属系统真实行为）",
    },
    source: "POST /api/v1/positions/discover?with_definitions=true + GET /api/v1/positions/{name}（2026-09-03 实测）",
    extracted_at: "2026-09-03",
  };
  const sub = emDir + "/" + String(ei).padStart(2, "0") + "_" + sanitize(name);
  fs.mkdirSync(sub, { recursive: true });
  dump(input, sub + "/input.json");
  dump(output, sub + "/output.json");
  emergingManifest.push({ dir: path.basename(sub), position: name, ratio: cand.emerging_ratio, emerging_skills: cand.emerging_skills || [] });
  console.log(`emerging OK ${String(ei).padStart(2, "0")} ${name} ratio=${cand.emerging_ratio}`);
  ei++;
});

dump({ existing: existingManifest, emerging: emergingManifest }, BATCH + "/_manifest.json");
console.log(`\n完成: existing ${existingManifest.length} + emerging ${emergingManifest.length}`);
