"""Skill name normalization: alias, vector, and source-count validation."""

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

SKILL_ALIAS: dict[str, list[str]] = {
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


_TAXONOMY_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "docs" / "ontology" / "skill_taxonomy.yaml"


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


_REVERSE_INDEX: dict[str, str] = {}
_LOCK = threading.Lock()


def _build_reverse_index() -> dict[str, str]:
    """Build alias-to-standard reverse lookup index."""
    idx = {}
    for standard, aliases in SKILL_ALIAS.items():
        for a in aliases:
            idx[a.lower()] = standard
        idx[standard.lower()] = standard
    return idx


_REVERSE_INDEX.update(_build_reverse_index())


# ---- YAML taxonomy integration ----
_YAML_SKILL_ALIASES = load_skill_aliases_from_yaml()
if _YAML_SKILL_ALIASES:
    merged = dict(_YAML_SKILL_ALIASES)
    for k, v in SKILL_ALIAS.items():
        if k not in merged:
            merged[k] = v
    SKILL_ALIAS.clear()
    SKILL_ALIAS.update(merged)
    logger.info(
        "Loaded {} skills from YAML + {} hardcoded = {} total",
        len(_YAML_SKILL_ALIASES),
        len(SKILL_ALIAS) - len(_YAML_SKILL_ALIASES),
        len(SKILL_ALIAS),
    )
    _REVERSE_INDEX.clear()
    _REVERSE_INDEX.update(_build_reverse_index())
else:
    logger.info("Using hardcoded skill aliases ({} skills)", len(SKILL_ALIAS))


def normalize_by_alias(skill_name: str) -> str | None:
    """Normalize a skill name using the alias dictionary.

    Args:
        skill_name: Raw skill name.

    Returns:
        Standardized skill name, or None if not found.
    """
    key = skill_name.strip().lower()
    return _REVERSE_INDEX.get(key)


CHROMA_COLLECTION_NAME: str = "skill_embeddings"
_SENTENCE_MODEL: Any = None
_SENTENCE_MODEL_NAME: str = "all-MiniLM-L6-v2"


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
    """
    try:
        import chromadb
    except ImportError:
        logger.warning("chromadb not installed, skipping vector normalization")
        return None

    if chroma_client is None:
        from app.config import settings
        chroma_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)

    collection_name = CHROMA_COLLECTION_NAME

    try:
        collection = chroma_client.get_collection(collection_name)
    except Exception:
        logger.warning("Chroma collection '{}' not found, skipping vector norm", collection_name)
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


def validate_skill_by_source_count(skill_name: str, min_sources: int = 3) -> bool:
    """Validate a skill by checking if it appears in enough source documents.

    Args:
        skill_name: Skill name to validate.
        min_sources: Minimum number of sources required.

    Returns:
        True if the skill meets the source count threshold.
    """
    if min_sources <= 1:
        return True
    standard = normalize_by_alias(skill_name)
    return standard is not None


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
    use_vector: bool = False,
    chroma_client: Any = None,
    vector_threshold: float = 0.85,
    min_sources: int = 3,
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
        result.is_valid = validate_skill_by_source_count(step, min_sources)
        return result

    if use_vector:
        vec = normalize_by_vector(skill_name, chroma_client, vector_threshold)
        if vec is not None:
            result.normalized = vec
            result.method = "vector"
            result.confidence = vector_threshold
            result.is_valid = validate_skill_by_source_count(vec, min_sources)
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
    use_vector: bool = False,
    chroma_client: Any = None,
    vector_threshold: float = 0.85,
    min_sources: int = 3,
) -> list[NormalizationResult]:
    """Normalize multiple skill names.

    Args:
        skill_names: List of raw skill names.
        use_vector: Enable vector-based fallback.
        chroma_client: ChromaDB client.
        vector_threshold: Vector similarity threshold.
        min_sources: Minimum source count.

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
        )
        for s in skill_names
    ]


def build_alias_reverse_index() -> dict[str, str]:
    """Build and return the alias-to-standard reverse index (thread-safe)."""
    with _LOCK:
        idx = _build_reverse_index()
        _REVERSE_INDEX.clear()
        _REVERSE_INDEX.update(idx)
        return dict(_REVERSE_INDEX)


def get_standard_skill_seeds() -> list[str]:
    """Return the list of standard (canonical) skill names.

    Useful for seeding ChromaDB collections or building UI dropdowns.
    """
    return sorted(SKILL_ALIAS.keys())
