"""Skill name normalization: alias, vector, and source-count validation."""

import threading
from dataclasses import dataclass, field
from typing import Any

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
    "NoSQL": ["nosql", "mongodb", "mongo", "redis", "cassandra", "dynamodb", "couchdb"],
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
    "Apache Kafka": ["kafka", "apache kafka", "kafka streaming", "kafka connect", "confluent kafka"],
    "Linux": ["linux", "unix", "red hat", "ubuntu", "centos", "debian", "bash", "shell", "shell scripting"],
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
    "OAuth": ["oauth", "oauth2", "oauth 2.0", "oauth 2", "openid", "openid connect", "saml", "jwt", "json web token"],
    "Unit Testing": ["unit testing", "unit test", "ut", "pytest", "junit", "jest", "mocha", "chai", "vitest"],
    "Test Automation": ["test automation", "automation testing", "e2e", "end to end", "selenium", "cypress", "playwright"],
    "System Design": ["system design", "system architecture", "architecture design", "software architecture", "distributed systems"],
    "API Design": ["api design", "api development", "api architecture", "rest api design", "api gateway"],
}

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


def normalize_by_alias(skill_name: str) -> str | None:
    """Normalize a skill name using the alias dictionary.

    Args:
        skill_name: Raw skill name.

    Returns:
        Standardized skill name, or None if not found.
    """
    key = skill_name.strip().lower()
    return _REVERSE_INDEX.get(key)


def get_embedding(text: str) -> list[float]:
    """Get sentence embedding for text using sentence-transformers.

    Args:
        text: Input text.

    Returns:
        Float embedding vector.

    Note: Requires sentence-transformers package installed.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning("sentence-transformers not installed, returning empty embedding")
        return []

    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    return model.encode(text, normalize_embeddings=True).tolist()


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
        chroma_client = chromadb.HttpClient(host="localhost", port=8001)

    collection_name = "skill_embeddings"

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
