"""Normalize — 技能标准化：别名映射、向量相似度、来源数验证和熟练度归一化。

核心流程（三步标准化管道）：
1. 别名查找（快速精确匹配）→ 2. 向量相似度（模糊匹配）→ 3. 来源数验证

业务价值：
  将 JD 中各种变体写法（如 "py", "python3", "Python 编程"）统一为标准技能名，
  确保后续匹配、分析、统计的准确性，避免同一技能因写法不同而被重复计数。
"""

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from app.config import settings
from app.exceptions import StarMapError

# ── Hardcoded alias dictionary (moved from module-level SKILL_ALIAS) ──
_HARDCODED_ALIASES: dict[str, list[str]] = {
    "Python": ["python", "python3", "python 3", "py", "python programming", "python dev", "python development"],
    "JavaScript": ["javascript", "js", "ecmascript", "es6", "es2015", "esnext", "node.js", "nodejs", "node", "deno"],
    "TypeScript": ["typescript", "ts", "type script"],
    "Java": ["java", "java8", "java11", "java17", "java ee", "jakarta ee", "j2ee"],
    "Go": ["go", "golang", "go lang"],
    "Rust": ["rust", "rust-lang", "rustlang"],
    "C++": ["c++", "cpp", "c plus plus", "c/c++", "c and c++"],
    "C#": ["c#", "csharp", "c sharp", ".net", "dotnet", "dot net", ".net core", "asp.net"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "pl/sql", "t-sql", "tsql", "sql server", "mssql"],
    "NoSQL": ["nosql", "dynamodb", "couchdb"],
    "React": ["react", "react.js", "reactjs", "react j", "react js", "react frontend", "next.js", "nextjs", "next"],
    "Vue.js": ["vue", "vue.js", "vuejs", "vue2", "vue3", "nuxt", "nuxt.js", "nuxtjs"],
    "Angular": ["angular", "angular.js", "angularjs", "angular2", "angular 2+"],
    "Docker": ["docker", "docker compose", "docker-compose", "container", "containers", "containerization"],
    "Kubernetes": ["kubernetes", "k8s", "kube", "k3s", "openshift"],
    "AWS": ["aws", "amazon web services", "ec2", "s3", "lambda", "aws lambda", "amazon s3", "aws ec2"],
    "Azure": ["azure", "microsoft azure", "azure devops", "azure functions", "azure cloud"],
    "GCP": ["gcp", "google cloud", "google cloud platform", "gce", "google compute engine", "gke"],
    "Git": ["git", "github", "gitlab", "bitbucket", "version control", "vcs", "scm"],
    "CI/CD": ["ci/cd", "ci cd", "cicd", "jenkins", "github actions", "gitlab ci", "circleci", "travis ci"],
    "Machine Learning": ["machine learning", "ml", "deep learning", "dl", "ml/dl", "statistical learning"],
    "Deep Learning": ["deep learning", "dl", "neural network", "neural networks", "nn", "dnn", "cnn", "rnn", "lstm", "transformer", "transformers"],
    "Natural Language Processing": ["nlp", "natural language processing", "text mining", "text analytics"],
    "Computer Vision": ["computer vision", "cv", "image processing", "object detection", "image recognition", "opencv"],
    "Data Science": ["data science", "data scientist", "data analytics", "data analysis", "analytics"],
    "TensorFlow": ["tensorflow", "tf", "tensor flow", "tensorflow2", "tf2"],
    "PyTorch": ["pytorch", "torch", "py-torch"],
    "FastAPI": ["fastapi", "fast api", "fast-api", "starlette"],
    "Flask": ["flask", "flask api", "flask restful", "flask-restful"],
    "Django": ["django", "django rest", "drf", "django rest framework"],
    "Spring Boot": ["spring boot", "springboot", "spring", "spring framework", "spring mvc", "spring cloud"],
    "GraphQL": ["graphql", "gql", "apollo", "apollo graphql", "relay"],
    "REST API": ["rest", "rest api", "restful", "restful api", "restful apis", "rest api design", "restful web services"],
    "gRPC": ["grpc", "g rpc", "protobuf", "protocol buffers"],
    "RabbitMQ": ["rabbitmq", "rabbit mq", "message queue", "mq", "message broker"],
    "Kafka": ["kafka", "apache kafka", "kafka message queue", "kafka mq", "kafka streaming", "kafka connect", "confluent kafka"],
    "Linux": ["linux", "unix", "red hat", "ubuntu", "centos", "debian", "bash", "shell scripting"],
    "Agile": ["agile", "scrum", "kanban", "scrum master", "agile development", "agile methodology"],
    "Project Management": ["project management", "pm", "project manager", "program management"],
    "Microservices": ["microservices", "micro service", "micro-service", "micro services architecture", "msa"],
    "Docker Swarm": ["docker swarm", "swarm", "docker swarm mode"],
    "Terraform": ["terraform", "iac", "infrastructure as code", "infrastructure-as-code"],
    "Ansible": ["ansible", "ansible playbook", "ansible tower", "ansible automation"],
    "Prometheus": ["prometheus", "prom", "prometheus monitoring"],
    "Grafana": ["grafana", "grafana dashboard"],
    "Elasticsearch": ["elasticsearch", "es", "elastic", "elastic stack", "elk", "elk stack"],
    "PostgreSQL": ["postgresql", "postgres", "pgsql", "pg"],
    "MongoDB": ["mongodb", "mongo", "mongoose", "mongod"],
    "Redis": ["redis", "redis cache", "redis cluster"],
    "Nginx": ["nginx", "nginx web server", "nginx proxy", "openresty"],
    "WebSocket": ["websocket", "ws", "wss", "websockets"],
    "OAuth": ["oauth", "oauth 2.0", "oauth 2", "openid", "openid connect", "saml", "json web token"],
    "Unit Testing": ["unit testing", "unit test", "ut", "pytest", "junit", "jest", "mocha", "chai", "vitest"],
    "Test Automation": ["test automation", "automation testing", "e2e", "end to end", "selenium", "cypress", "playwright"],
    "System Design": ["system design", "system architecture", "architecture design", "software architecture", "distributed systems"],
    "API Design": ["api design", "api development", "api architecture", "rest api design", "api gateway"],
    # ---- Frontend / UI ----
    "HTML5": ["html5", "html 5", "html"],
    "CSS3": ["css3", "css 3", "css", "cascading style sheets"],
    "Webpack": ["webpack", "web pack", "webpack5"],
    "Vite": ["vite", "vitejs", "vite.js", "vite build tool"],
    "Next.js": ["next.js", "nextjs", "next", "next js"],
    "Nuxt.js": ["nuxt.js", "nuxtjs", "nuxt"],
    "Tailwind CSS": ["tailwind css", "tailwindcss", "tailwind"],
    "Pinia": ["pinia", "pinia store", "pinia state management"],
    "Storybook": ["storybook", "story book"],
    "Three.js": ["three.js", "threejs", "three js", "webgl"],
    "WebAssembly": ["webassembly", "wasm", "web assembly"],
    # ---- Mobile ----
    "Kotlin": ["kotlin", "kotlin lang", "kotlin language"],
    "Swift": ["swift", "swift language", "swift programming"],
    "SwiftUI": ["swiftui", "swift ui"],
    "UIKit": ["uikit", "ui kit", "uikit framework"],
    "Flutter": ["flutter", "flutter framework", "flutter ui", "flutter sdk"],
    "Dart": ["dart", "dart lang", "dart language"],
    "Jetpack Compose": ["jetpack compose", "compose", "android compose", "jetpack compose ui"],
    "RxJava": ["rxjava", "rx java", "reactivex java"],
    "RxSwift": ["rxswift", "rx swift", "reactivex swift"],
    "Provider": ["provider", "provider state management", "flutter provider"],
    "BLoC": ["bloc", "bloc pattern", "bloc state management", "flutter bloc"],
    "Room": ["room", "room database", "android room"],
    "Core Data": ["core data", "coredata", "apple core data"],
    "Combine": ["combine", "apple combine", "combine framework"],
    "Firebase": ["firebase", "google firebase", "firebase console", "firebase sdk"],
    # ---- Big Data & Streaming ----
    "Spark": ["spark", "apache spark", "spark core", "spark sql", "spark streaming", "pyspark"],
    "Hadoop": ["hadoop", "apache hadoop", "hdfs", "mapreduce", "yarn"],
    "Hive": ["hive", "hive sql", "hive data warehouse"],
    "Flink": ["flink", "apache flink", "flink streaming"],
    "Airflow": ["airflow", "apache airflow", "airflow dag", "airflow pipeline"],
    "Presto": ["presto", "prestodb", "trino", "presto sql"],
    "HBase": ["hbase", "apache hbase", "hbase database"],
    "Delta Lake": ["delta lake", "delta lakehouse", "delta table"],
    "dbt": ["dbt", "dbt data build tool", "data build tool"],
    "Snowflake": ["snowflake", "snowflake cloud", "snowflake warehouse"],
    "ClickHouse": ["clickhouse", "click house", "clickhouse olap"],
    "TiDB": ["tidb", "ti db", "tikv", "pd"],
    # ---- ML / AI ----
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn", "sk learn"],
    "Transformers": ["transformers", "huggingface transformers", "hf transformers"],
    "BERT": ["bert", "bert model", "google bert", "bert nlp"],
    "spaCy": ["spacy", "spacy nlp", "spacy library"],
    "NLTK": ["nltk", "natural language toolkit"],
    "LangChain": ["langchain", "lang chain", "langchain framework"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    "LLM": ["llm", "large language model", "large language models"],
    "Prompt Engineering": ["prompt engineering", "prompt design", "prompt tuning", "prompt crafting", "prompt engineer"],
    "MLflow": ["mlflow", "ml flow", "mlflow tracking", "mlflow model"],
    "ONNX": ["onnx", "open neural network exchange", "onnx runtime"],
    "TensorRT": ["tensorrt", "tensor rt", "nvidia tensorrt"],
    "CUDA": ["cuda", "nvidia cuda", "cuda toolkit"],
    "ChromaDB": ["chromadb", "chroma db", "chroma vector db"],
    "Pinecone": ["pinecone", "pinecone vector db", "pinecone db"],
    "OpenCV": ["opencv", "open cv", "open computer vision"],
    # ---- Cloud / Service Mesh ----
    "Istio": ["istio", "istio service mesh", "istio mesh"],
    "Helm": ["helm", "helm chart", "helm charts", "helm package manager"],
    "ArgoCD": ["argocd", "argo cd", "argo cd gitops"],
    "Knative": ["knative", "knative serving", "knative eventing"],
    "Vault": ["vault", "hashicorp vault", "vault secret"],
    "Consul": ["consul", "hashicorp consul", "consul service discovery"],
    "Envoy": ["envoy", "envoy proxy", "envoy gateway"],
    "Kong": ["kong", "kong api gateway", "kong gateway"],
    "Seldon": ["seldon", "seldon core", "seldon model serving"],
    "Kubeflow": ["kubeflow", "kube flow", "kubeflow pipeline"],
    "Yocto": ["yocto", "yocto project", "yocto build system"],
    # ---- Languages ----
    "Ruby": ["ruby", "ruby language", "ruby programming"],
    "PHP": ["php", "php language", "php programming"],
    "Scala": ["scala", "scala language", "scala programming"],
    "ABAP": ["abap", "sap abap", "abap programming"],
    "Shell": ["shell", "shell script", "shell scripting", "bash scripting"],
    "Markdown": ["markdown", "md", "markdown documentation"],
    # ---- Protocols & Hardware ----
    "WebRTC": ["webrtc", "web rtc", "webrtc protocol"],
    "SIP": ["sip", "sip protocol", "session initiation protocol"],
    "UART": ["uart", "universal asynchronous receiver transmitter"],
    "I2C": ["i2c", "i2c bus", "i2c protocol", "iic"],
    "SPI": ["spi", "spi bus", "spi protocol", "serial peripheral interface"],
    "ARM": ["arm", "arm architecture", "arm cortex", "arm mcu"],
    "RTOS": ["rtos", "real time os", "real time operating system"],
    "FreeRTOS": ["freertos", "free rtos", "free real time os"],
    "Zephyr": ["zephyr", "zephyr os", "zephyr rtos"],
    # 2026-08-15 F1 优化: 补嵌入式/测试域技能 — dict 后过滤只保留词汇表内技能，
    # 词汇表外真技能被误删（评估 F1 0.857 主因：Communication Protocols 等 4 项漏检）。
    "Embedded Linux": ["embedded linux", "embedded linux development", "embedded linux system"],
    "Microcontrollers": ["microcontrollers", "microcontroller", "mcu", "stm32", "esp32"],
    "Assembly": ["assembly", "assembly language", "assembly programming"],
    "Communication Protocols": ["communication protocols", "communication protocol", "comm protocols"],
    "PCB Design": ["pcb design", "pcb layout", "pcb design tool"],
    "Debugging": ["debugging", "debugger", "gdb", "kernel debugging"],
    "Testing": ["testing", "software testing", "unit testing", "integration testing", "自动化测试"],
    # ---- Blockchain ----
    "Solidity": ["solidity", "solidity lang", "solidity contract"],
    "Ethereum": ["ethereum", "eth", "ethereum blockchain"],
    "Web3.js": ["web3.js", "web3js", "web3 js", "web3"],
    "IPFS": ["ipfs", "interplanetary file system", "ipfs storage"],
    "Hardhat": ["hardhat", "hardhat framework", "hardhat ethereum"],
    "Substrate": ["substrate", "substrate framework", "parity substrate"],
    "Zero-Knowledge": ["zero knowledge", "zk", "zero knowledge proof", "zkp"],
    # ---- Testing ----
    "Playwright": ["playwright", "playwright testing", "playwright automation"],
    "Postman": ["postman", "postman api", "postman testing"],
    "Locust": ["locust", "locust testing", "locust load testing"],
    "Jest": ["jest", "jest testing", "jest framework"],
    "pytest": ["pytest", "py test", "pytest testing"],
    "Cypress": ["cypress", "cypress testing", "cypress e2e"],
    # ---- Build & Tools ----
    "Gradle": ["gradle", "gradle build", "gradle tool"],
    "Xcode": ["xcode", "xcode ide", "xcode development"],
    "Swagger": ["swagger", "swagger ui", "swagger openapi", "swagger api"],
    "Sphinx": ["sphinx", "sphinx docs", "sphinx documentation"],
    "Docusaurus": ["docusaurus", "docusaurus docs", "docusaurus documentation"],
    "Cargo": ["cargo", "cargo build", "cargo rust", "cargo package manager"],
    # ---- BI & Design ----
    "Tableau": ["tableau", "tableau bi", "tableau visualization"],
    "Power BI": ["power bi", "powerbi", "power bi dashboard"],
    "Excel": ["excel", "microsoft excel", "ms excel", "excel spreadsheet"],
    "Axure": ["axure", "axure rp", "axure prototype"],
    "Figma": ["figma", "figma design", "figma prototyping"],
    # ---- Game & 3D ----
    "Unity": ["unity", "unity 3d", "unity engine", "unity game engine"],
    "Unreal": ["unreal", "unreal engine", "unreal engine 4", "unreal engine 5"],
    "OpenXR": ["openxr", "open xr", "openxr standard"],
    "ARKit": ["arkit", "ar kit", "apple arkit"],
    "ARCore": ["arcore", "ar core", "google arcore"],
    "Blender": ["blender", "blender 3d", "blender modeling"],
    "Qt": ["qt", "qt framework", "qt gui"],
    "WPF": ["wpf", "wpf framework", "windows presentation foundation"],
    # ---- Chinese skill names ----
    "项目管理": ["项目管理", "项目 管理", "project management"],
    "数据分析": ["数据分析", "数据 分析", "data analysis"],
    "系统架构": ["系统架构", "系统 架构", "系统架构设计", "system architecture"],
    "团队管理": ["团队管理", "团队 管理", "team management", "people management"],
    "性能优化": ["性能优化", "性能 优化", "performance optimization", "performance tuning"],
    "技术写作": ["技术写作", "技术 写作", "technical writing"],
    "用户调研": ["用户调研", "用户 调研", "user research"],
    "产品设计": ["产品设计", "产品 设计", "product design"],
    "统计分析": ["统计分析", "统计 分析", "statistical analysis"],
    "微服务": ["微服务", "微服务架构"],
    "微前端": ["微前端", "微前端架构", "micro frontend"],
    "领域驱动设计": ["领域驱动设计", "ddd", "领域驱动"],
    "异步编程": ["异步编程", "异步 编程", "async programming", "asynchronous programming"],
    "多线程": ["多线程", "多线程编程", "multi threading", "multithreading"],
    "前端工程化": ["前端工程化", "前端 工程化", "frontend engineering"],
    "可视化编辑器": ["可视化编辑器", "可视化 编辑器", "visual editor", "visual builder"],
    "推荐系统": ["推荐系统", "推荐 系统", "recommendation system", "recommender system"],
    "渗透测试": ["渗透测试", "渗透 测试", "pentest"],
    "Web安全": ["web安全", "web安全"],
    "智能合约": ["智能合约", "智能 合约", "smart contract"],
    "嵌入式开发": ["嵌入式开发", "嵌入式", "embedded development", "embedded system"],
    # ---- Education aliases ----
    "计算机视觉": ["计算机视觉"],
    "自然语言处理": ["自然语言处理"],
    "Element Plus": ["element plus", "element-plus", "elementplus", "element ui", "element-ui"],
    "Celery": ["celery", "celery task", "celery queue"],
    "SAP HANA": ["sap hana", "sap hana db", "hana", "hana db"],
    "FFmpeg": ["ffmpeg", "ffmpeg encoder", "ffmpeg decoder"],
    "GStreamer": ["gstreamer", "gst", "gstreamer pipeline"],
    "MyBatis": ["mybatis", "mybatis plus", "mybatis-plus", "mybatis3"],
    "Nacos": ["nacos", "nacos config", "nacos discovery", "nacos registry"],
    "Sentinel": ["sentinel", "sentinel flow", "sentinel circuit breaker"],
    "Canal": ["canal", "canal binlog", "canal mysql"],
    "Matplotlib": ["matplotlib", "matplotlib plot", "mpl"],
}


# Try multiple paths: Docker container, host, and env override
_TAXONOMY_CANDIDATES = [
    Path(__file__).resolve().parent.parent.parent.parent.parent / "docs" / "ontology" / "skill_taxonomy.yaml",
    Path(__file__).resolve().parents[4] / "docs" / "ontology" / "skill_taxonomy.yaml",
    Path("/app/docs/ontology/skill_taxonomy.yaml"),
    Path(__file__).resolve().parents[3] / "docs" / "ontology" / "skill_taxonomy.yaml",
]
_TAXONOMY_PATH = next((p for p in _TAXONOMY_CANDIDATES if p.exists()), _TAXONOMY_CANDIDATES[0])


def load_skill_aliases_from_yaml(path: Path = _TAXONOMY_PATH) -> dict[str, list[str]]:
    if not path.exists():
        logger.warning("Skill taxonomy not found at {}", path)
        return {}

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    aliases: dict[str, list[str]] = {}
    ontology = data.get("ontology", {})
    for domain in ontology.get("domains", []):
        for sub in domain.get("subdomains", []):
            for skill in sub.get("skills", []):
                name = skill.get("name", "")
                alias_list = skill.get("aliases", [])
                if name:
                    aliases[name] = alias_list
    return aliases


# ── SkillNormalizer class ──


class SkillNormalizer:
    """Skill name normalization with alias resolution.

    Encapsulates the alias dictionary and reverse index, providing
    alias lookup, dictionary extraction, and reverse index rebuild.
    """

    def __init__(self) -> None:
        self._aliases: dict[str, list[str]] = {}
        self._reverse_index: dict[str, str] = {}
        self._dict_pairs: list[tuple[str, str]] = []
        self._lock = threading.Lock()
        self._load_builtin_aliases()

    def _load_builtin_aliases(self) -> None:
        """Load hardcoded skill aliases and merge with YAML taxonomy."""
        self._aliases = dict(_HARDCODED_ALIASES)

        yaml_aliases = load_skill_aliases_from_yaml()
        if yaml_aliases:
            merged = dict(yaml_aliases)
            for k, v in self._aliases.items():
                if k not in merged:
                    merged[k] = v
            self._aliases.clear()
            self._aliases.update(merged)
            logger.info(
                "Loaded {} skills from YAML + {} hardcoded = {} total",
                len(yaml_aliases),
                len(self._aliases) - len(yaml_aliases),
                len(self._aliases),
            )
        else:
            logger.info("Using hardcoded skill aliases ({} skills)", len(self._aliases))

        self._reverse_index = self._build_reverse_index()

    def normalize_by_alias(self, skill_name: str) -> str | None:
        """Normalize a skill name using the alias dictionary.

        Args:
            skill_name: Raw skill name.

        Returns:
            Standardized skill name, or None if not found.
        """
        key = skill_name.strip().lower()
        return self._reverse_index.get(key)

    def get_aliases(self, skill_name: str) -> list[str]:
        """Get all aliases for a canonical skill name.

        Args:
            skill_name: Canonical skill name.

        Returns:
            List of alias strings, or empty list if not found.
        """
        return self._aliases.get(skill_name, [])

    def get_standard_skill_seeds(self) -> list[str]:
        """Return the list of standard (canonical) skill names.

        Useful for seeding ChromaDB collections or building UI dropdowns.
        """
        return sorted(self._aliases.keys())

    def build_reverse_index(self) -> dict[str, str]:
        """Build and return the alias-to-standard reverse index (thread-safe)."""
        with self._lock:
            idx = self._build_reverse_index()
            self._reverse_index.clear()
            self._reverse_index.update(idx)
            return dict(self._reverse_index)

    def _build_reverse_index(self) -> dict[str, str]:
        """Build alias-to-standard reverse lookup index."""
        idx = {}
        for standard, aliases in self._aliases.items():
            for a in aliases:
                idx[a.lower()] = standard
            idx[standard.lower()] = standard
        return idx

    def _build_dict_pairs(self) -> list[tuple[str, str]]:
        """Build and cache sorted alias-canonical pairs for dictionary extraction."""
        if self._dict_pairs:
            return self._dict_pairs
        pairs: list[tuple[str, str]] = []
        for canonical, aliases in self._aliases.items():
            for alias in aliases:
                pairs.append((alias, canonical))
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        self._dict_pairs = pairs
        return pairs

    def extract_dict_skills(self, text: str) -> set[str]:
        """Extract skill names found in text via dictionary (SKILL_ALIAS) match.

        Returns a set of canonical skill names. Used as a high-precision pre-filter
        before LLM extraction — anything matched here is treated as a verified skill,
        and the LLM is then asked only to find ADDITIONAL skills not already found.

        Args:
            text: Raw JD or resume text.

        Returns:
            Set of canonical skill names (e.g. {"Python", "FastAPI", "Docker"}).
        """
        if not text:
            return set()
        pairs = self._build_dict_pairs()
        found: set[str] = set()
        text_lower = text.lower()
        for alias, canonical in pairs:
            if not alias:
                continue
            idx = text_lower.find(alias.lower())
            if idx < 0:
                continue
            # Word boundary check: prev/next char must NOT be an ASCII identifier
            # char (avoid "Go" inside "Google", "Java" inside "JavaScript"). Chinese
            # characters return True for str.isalnum() so we explicitly use the
            # ASCII set only.
            # P0-AUDIT-FIX (2026-08-13): wrap each OR clause in parens so the
            # precedence is `(prev.isascii() AND prev.isalnum()) OR prev in "_+#"`
            # instead of `prev.isascii() AND (prev.isalnum() OR prev in "_+#")`.
            # Without parens, "Go" inside "Google" would match (G is alnum),
            # and "Java" inside "JavaScript" would match — silently inflating F1.
            prev_char = text_lower[idx - 1] if idx > 0 else " "
            next_idx = idx + len(alias)
            next_char = text_lower[next_idx] if next_idx < len(text_lower) else " "
            if (prev_char.isascii() and prev_char.isalnum()) or prev_char in "_+#":
                continue
            if (next_char.isascii() and next_char.isalnum()) or next_char in "_+#":
                continue
            found.add(canonical)
        return found


# Pre-compile alias list at import time for fast dictionary extraction.
# ponytail: aliases sorted by length DESC so "Apache Kafka" matches before "Kafka"
# and "PostgreSQL" matches before "SQL". The earlier regex-with-named-groups
# approach blew Python's 100-group limit (2066 aliases > 100), so we fall back
# to a sorted alias list + simple substring scan. With ~3000 aliases per JD,
# a full scan is ~1ms — well under any LLM call cost.

# ── Singleton instance & backward-compatible references ──

_normalizer = SkillNormalizer()

# Backward-compatible module-level reference to the alias dictionary.
# Any code that does `from app.core.extraction.normalize import SKILL_ALIAS`
# still works; the dict is now owned by the singleton.
SKILL_ALIAS: dict[str, list[str]] = _normalizer._aliases


def normalize_by_alias(skill_name: str) -> str | None:
    """Normalize a skill name using the alias dictionary.

    Delegates to SkillNormalizer singleton.

    Args:
        skill_name: Raw skill name.

    Returns:
        Standardized skill name, or None if not found.
    """
    return _normalizer.normalize_by_alias(skill_name)


def extract_dict_skills(text: str) -> set[str]:
    """Extract skill names found in text via dictionary (SKILL_ALIAS) match.

    Delegates to SkillNormalizer singleton.

    Args:
        text: Raw JD or resume text.

    Returns:
        Set of canonical skill names.
    """
    return _normalizer.extract_dict_skills(text)


def get_standard_skill_seeds() -> list[str]:
    """Return the list of standard (canonical) skill names.

    Delegates to SkillNormalizer singleton.
    """
    return _normalizer.get_standard_skill_seeds()


def build_alias_reverse_index() -> dict[str, str]:
    """Build and return the alias-to-standard reverse index (thread-safe).

    Delegates to SkillNormalizer singleton.
    """
    return _normalizer.build_reverse_index()


# ── ChromaDB / vector normalization ──

CHROMA_COLLECTION_NAME: str = "skill_embeddings"
_SENTENCE_MODEL: Any = None
_SENTENCE_MODEL_NAME: str = "BAAI/bge-m3"

# 业务说明：ChromaDB 不可用负缓存。当 ChromaDB 连接失败或 collection 不存在时，
# 在 _CHROMA_NEGATIVE_CACHE_TTL 秒内直接快速返回，避免每次调用都重新建连/查询。
# 技术说明：匹配引擎的 _chroma_similarity 会在 O(目标技能×候选技能) 的嵌套循环中
# 调用 normalize_by_vector，若每次都重新尝试连接，单次匹配会触发数百次失败重试，
# 导致 /match/position 接口长时间无响应（前端表现为"点击开始诊断无反馈"）。
# 负缓存 TTL 60s 平衡了"故障快速失败"与"恢复后自动重试"两个诉求。
_CHROMA_NEGATIVE_CACHE_TTL: float = 60.0
_chroma_unavailable_until: float = 0.0
_chroma_unavailable_reason: str = ""


def _is_chroma_marked_unavailable() -> bool:
    """Return True if ChromaDB is marked unavailable within the negative-cache window."""
    import time

    return time.monotonic() < _chroma_unavailable_until


def _mark_chroma_unavailable(reason: str) -> None:
    """Mark ChromaDB as unavailable for the negative-cache TTL window."""
    import time

    global _chroma_unavailable_until, _chroma_unavailable_reason
    _chroma_unavailable_until = time.monotonic() + _CHROMA_NEGATIVE_CACHE_TTL
    _chroma_unavailable_reason = reason


def reset_chroma_cache() -> None:
    """Reset the ChromaDB negative cache (for tests / manual recovery)."""
    global _chroma_unavailable_until, _chroma_unavailable_reason
    _chroma_unavailable_until = 0.0
    _chroma_unavailable_reason = ""


def get_embedding(text: str) -> list[float]:
    """Get sentence embedding for text using sentence-transformers.

    The SentenceTransformer model is lazily cached at module level.

    Args:
        text: Input text.

    Returns:
        Float embedding vector.

    Note: Requires sentence-transformers package installed.
    """
    global _SENTENCE_MODEL
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning("sentence-transformers not installed, returning empty embedding")
        return []

    if _SENTENCE_MODEL is None:
        logger.info("Loading SentenceTransformer model: {}", _SENTENCE_MODEL_NAME)
        _SENTENCE_MODEL = SentenceTransformer(_SENTENCE_MODEL_NAME, device="cpu")
    return _SENTENCE_MODEL.encode(text, normalize_embeddings=True).tolist()


def normalize_by_vector(
    skill_name: str,
    chroma_client: Any = None,
    threshold: float = 0.85,
) -> str | None:
    """Normalize skill name via vector similarity search.

    Args:
        skill_name: Raw skill name.
        chroma_client: ChromaDB client instance. If None, creates a default one.
        threshold: Similarity threshold (cosine).

    Returns:
        Matched standard skill name, or None.

    Note: When ChromaDB is unreachable or the collection is missing, the failure
    is cached for ``_CHROMA_NEGATIVE_CACHE_TTL`` seconds to avoid hammering the
    service from hot loops (e.g. the match engine's O(N×M) chroma fallback).
    """
    # 负缓存快速失败：若 ChromaDB 近期被标记为不可用，直接返回 None，
    # 避免在匹配引擎嵌套循环中重复触发连接/查询失败。
    # 注意：显式传入 chroma_client 的调用（如管理脚本）跳过负缓存，以便即时验证。
    if chroma_client is None and _is_chroma_marked_unavailable():
        return None

    try:
        import chromadb
    except ImportError:
        logger.warning("chromadb not installed, skipping vector normalization")
        _mark_chroma_unavailable("chromadb-not-installed")
        return None

    if chroma_client is None:
        try:
            from app.config import settings
            chroma_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        except StarMapError:
            raise
        except Exception:
            logger.warning("ChromaDB not reachable, skipping vector normalization")
            _mark_chroma_unavailable("client-unreachable")
            return None

    collection_name = CHROMA_COLLECTION_NAME

    try:
        collection = chroma_client.get_collection(collection_name)
    except StarMapError:
        raise
    except Exception:
        # 仅在首次失败时记录 warning + 标记不可用；负缓存窗口内后续调用静默返回 None。
        if not _is_chroma_marked_unavailable():
            logger.warning("Chroma collection '{}' not found, skipping vector norm", collection_name)
            _mark_chroma_unavailable(f"collection-missing:{collection_name}")
        return None

    query_embedding = get_embedding(skill_name)
    if not query_embedding:
        return None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=1,
        include=["distances", "metadatas"],
    )

    if not results["distances"] or not results["distances"][0]:
        return None

    distance = results["distances"][0][0]
    similarity = 1.0 - distance

    if similarity >= threshold:
        metadata = results["metadatas"][0][0] if results.get("metadatas") else {}
        return metadata.get("standard_name") if metadata else None

    return None


def validate_skill_by_source_count(
    skill_name: str,
    min_sources: int = 3,
    source_counts: dict[str, int] | None = None,
) -> bool:
    """Validate a skill by checking if it appears in enough source documents.

    Args:
        skill_name: Skill name to validate.
        min_sources: Minimum number of sources required.
        source_counts: Optional dict mapping skill name -> source count.
            If provided, uses real counts instead of alias existence check.

    Returns:
        True if the skill meets the source count threshold.
    """
    if min_sources <= 1:
        return True
    if source_counts is not None:
        standard = normalize_by_alias(skill_name) or skill_name
        count = source_counts.get(standard, 0)
        return count >= min_sources
    # Fallback: alias existence check when no source_counts available
    matched = normalize_by_alias(skill_name)
    return matched is not None


# ── Normalization pipeline ──


@dataclass
class NormalizationResult:
    """Result of a skill normalization operation."""

    original: str
    normalized: str | None = None
    method: str = "none"
    confidence: float = 0.0
    is_valid: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


def normalize_skill(
    skill_name: str,
    use_vector: bool = True,
    chroma_client: Any = None,
    vector_threshold: float = settings.extraction_vector_threshold,
    min_sources: int = settings.extraction_min_sources,
    source_counts: dict[str, int] | None = None,
) -> NormalizationResult:
    """Normalize a skill name through a 3-step pipeline.

    Pipeline:
        1. Alias lookup (fast, exact match).
        2. Vector similarity (if alias fails and use_vector=True).
        3. Source count validation.

    Args:
        skill_name: Raw skill name.
        use_vector: Whether to attempt vector-based normalization on alias miss.
        chroma_client: ChromaDB client for vector lookup.
        vector_threshold: Cosine similarity threshold for vector match.
        min_sources: Minimum source count for validation.

    Returns:
        NormalizationResult dataclass.
    """
    result = NormalizationResult(original=skill_name)

    step = normalize_by_alias(skill_name)
    if step is not None:
        result.normalized = step
        result.method = "alias"
        result.confidence = 0.95
        result.is_valid = validate_skill_by_source_count(step, min_sources, source_counts)
        return result

    if use_vector:
        vec = normalize_by_vector(skill_name, chroma_client, vector_threshold)
        if vec is not None:
            result.normalized = vec
            result.method = "vector"
            result.confidence = vector_threshold
            result.is_valid = validate_skill_by_source_count(vec, min_sources, source_counts)
            return result

    result.normalized = skill_name
    result.method = "identity"
    result.confidence = 0.5
    result.is_valid = True
    result.metadata["note"] = "No alias or vector match found; kept original"
    logger.debug("No normalization found for '{}', keeping original", skill_name)
    return result


def batch_normalize_skills(
    skill_names: list[str],
    use_vector: bool = True,
    chroma_client: Any = None,
    vector_threshold: float = settings.extraction_vector_threshold,
    min_sources: int = settings.extraction_min_sources,
    source_counts: dict[str, int] | None = None,
) -> list[NormalizationResult]:
    """Normalize multiple skill names.

    Args:
        skill_names: List of raw skill names.
        use_vector: Enable vector-based fallback.
        chroma_client: ChromaDB client.
        vector_threshold: Vector similarity threshold.
        min_sources: Minimum source count.
        source_counts: Optional dict mapping skill name -> source count
            for validating source frequency requirements.

    Returns:
        List of NormalizationResult.
    """
    return [
        normalize_skill(
            s,
            use_vector=use_vector,
            chroma_client=chroma_client,
            vector_threshold=vector_threshold,
            min_sources=min_sources,
            source_counts=source_counts,
        )
        for s in skill_names
    ]


# ── Proficiency normalization ──
_EXPERT_TERMS = frozenset({"精通", "expert", "advanced", "senior", "high"})
_BEGINNER_TERMS = frozenset({"了解", "beginner", "basic", "junior", "low"})


def normalize_proficiency(value: Any) -> str:
    """Normalize proficiency/level descriptions to canonical Chinese: 精通/熟悉/了解.

    Handles Chinese and English terms from JD extraction and Neo4j node properties.
    Default falls to '熟悉' (intermediate).
    """
    raw = str(value or "").strip().lower()
    if raw in _EXPERT_TERMS:
        return "精通"
    if raw in _BEGINNER_TERMS:
        return "了解"
    return "熟悉"
