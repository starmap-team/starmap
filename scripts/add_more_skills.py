"""Add additional skills to reach ≥500 target."""
import asyncio
from neo4j import AsyncGraphDatabase

# Additional skills from ESCO taxonomy and common IT skills
EXTRA_SKILLS = [
    # Programming languages not yet covered
    ("Erlang", "编程语言"), ("Haskell", "编程语言"), ("Clojure", "编程语言"),
    ("Julia", "编程语言"), ("Elixir", "编程语言"), ("Groovy", "编程语言"),
    ("Perl", "编程语言"), ("Objective-C", "编程语言"), ("COBOL", "编程语言"),
    ("Fortran", "编程语言"), ("Pascal", "编程语言"), ("MATLAB", "编程语言"),
    ("VHDL", "编程语言"), ("Verilog", "编程语言"), ("ABAP", "编程语言"),
    ("RPG", "编程语言"), ("Ada", "编程语言"), ("Scheme", "编程语言"),
    ("Prolog", "编程语言"), ("Lisp", "编程语言"), ("F#", "编程语言"),
    ("OCaml", "编程语言"), ("Crystal", "编程语言"), ("Nim", "编程语言"),
    ("Zig", "编程语言"), ("V", "编程语言"), ("Carbon", "编程语言"),
    # Frontend frameworks and tools
    ("Ember.js", "前端开发"), ("Backbone.js", "前端开发"), ("jQuery", "前端开发"),
    ("Material-UI", "前端开发"), ("Ant Design", "前端开发"), ("Chakra UI", "前端开发"),
    ("Styled Components", "前端开发"), ("Storybook", "前端开发"), ("Cypress", "前端开发"),
    ("Jest", "前端开发"), ("Mocha", "前端开发"), ("Chai", "前端开发"),
    ("ESBuild", "前端开发"), ("Rollup", "前端开发"), ("Parcel", "前端开发"),
    ("Babel", "前端开发"), ("Prettier", "前端开发"), ("Three.js", "前端开发"),
    ("D3.js", "前端开发"), ("Chart.js", "前端开发"), ("ECharts", "前端开发"),
    ("Highcharts", "前端开发"), ("Mapbox", "前端开发"), ("Leaflet", "前端开发"),
    ("PWA", "前端开发"), ("WebAssembly", "前端开发"), ("WebGL", "前端开发"),
    ("WebSocket", "前端开发"), ("Service Worker", "前端开发"),
    # Backend frameworks and tools
    ("Spring Cloud", "后端开发"), ("Spring Security", "后端开发"),
    ("MyBatis", "后端开发"), ("Hibernate", "后端开发"), ("JPA", "后端开发"),
    ("Micronaut", "后端开发"), ("Quarkus", "后端开发"), ("Vert.x", "后端开发"),
    ("Actix", "后端开发"), ("Rocket", "后端开发"), ("Axum", "后端开发"),
    ("Echo", "后端开发"), ("Fiber", "后端开发"), ("Buffalo", "后端开发"),
    ("Phoenix", "后端开发"), ("NestJS", "后端开发"), ("AdonisJS", "后端开发"),
    ("Strapi", "后端开发"), ("Directus", "后端开发"), ("Hasura", "后端开发"),
    ("Prisma", "后端开发"), ("Sequelize", "后端开发"), ("TypeORM", "后端开发"),
    ("Mongoose", "后端开发"), ("SQLAlchemy", "后端开发"), ("Django ORM", "后端开发"),
    ("Retrofit", "后端开发"), ("Feign", "后端开发"), ("WebClient", "后端开发"),
    # Databases
    ("DynamoDB", "数据库"), ("CosmosDB", "数据库"), ("CouchDB", "数据库"),
    ("Neo4j", "数据库"), ("ArangoDB", "数据库"), ("JanusGraph", "数据库"),
    ("InfluxDB", "数据库"), ("TimescaleDB", "数据库"), ("QuestDB", "数据库"),
    ("CockroachDB", "数据库"), ("TiDB", "数据库"), ("OceanBase", "数据库"),
    ("Vitess", "数据库"), ("PlanetScale", "数据库"), ("Supabase", "数据库"),
    ("Firebase Realtime Database", "数据库"), ("Realm", "数据库"),
    ("Druid", "数据库"), ("Pinot", "数据库"), ("Kylin", "数据库"),
    ("Memcached", "数据库"), ("Valkey", "数据库"), ("KeyDB", "数据库"),
    ("RocksDB", "数据库"), ("LevelDB", "数据库"), ("LMDB", "数据库"),
    # Cloud and DevOps
    ("Pulumi", "云原生"), ("CDK", "云原生"), ("Serverless Framework", "云原生"),
    ("OpenShift", "云原生"), ("Rancher", "云原生"), ("K3s", "云原生"),
    ("Podman", "云原生"), ("Buildah", "云原生"), ("Skopeo", "云原生"),
    ("containerd", "云原生"), ("CRI-O", "云原生"), ("FluxCD", "云原生"),
    ("ArgoCD", "云原生"), ("Tekton", "云原生"), ("Spinnaker", "云原生"),
    ("Consul", "云原生"), ("Vault", "云原生"), ("Nomad", "云原生"),
    ("Envoy", "云原生"), ("Linkerd", "云原生"), ("Cilium", "云原生"),
    ("Calico", "云原生"), ("Flannel", "云原生"), ("Weave", "云原生"),
    ("Thanos", "云原生"), ("Cortex", "云原生"), ("Loki", "云原生"),
    ("Tempo", "云原生"), ("Mimir", "云原生"), ("Jaeger", "云原生"),
    ("Zipkin", "云原生"), ("OpenTelemetry", "云原生"), ("Datadog", "云原生"),
    ("New Relic", "云原生"), ("Splunk", "云原生"), ("ELK Stack", "云原生"),
    # AI/ML additional
    ("JAX", "AI/机器学习"), ("Keras", "AI/机器学习"), ("FastAI", "AI/机器学习"),
    ("Lightning", "AI/机器学习"), ("Ray", "AI/机器学习"), ("Dask", "AI/机器学习"),
    ("RAPIDS", "AI/机器学习"), ("Modin", "AI/机器学习"), ("Vaex", "AI/机器学习"),
    ("Weights & Biases", "AI/机器学习"), ("Neptune", "AI/机器学习"),
    ("ClearML", "AI/机器学习"), ("DVC", "AI/机器学习"), ("CML", "AI/机器学习"),
    ("Seldon", "AI/机器学习"), ("BentoML", "AI/机器学习"), ("TorchServe", "AI/机器学习"),
    ("Triton", "AI/机器学习"), ("TensorRT", "AI/机器学习"), ("OpenVINO", "AI/机器学习"),
    ("CoreML", "AI/机器学习"), ("TFLite", "AI/机器学习"), ("MediaPipe", "AI/机器学习"),
    ("Stable Diffusion", "AI/机器学习"), ("Midjourney", "AI/机器学习"),
    ("DALL-E", "AI/机器学习"), ("Whisper", "AI/机器学习"), ("CLIP", "AI/机器学习"),
    ("LLaMA", "AI/机器学习"), ("Mistral", "AI/机器学习"), ("Gemma", "AI/机器学习"),
    ("Qwen", "AI/机器学习"), ("DeepSeek", "AI/机器学习"), ("Yi", "AI/机器学习"),
    ("Anthropic API", "AI/机器学习"), ("Cohere", "AI/机器学习"), ("AI21", "AI/机器学习"),
    ("Haystack", "AI/机器学习"), ("Semantic Kernel", "AI/机器学习"),
    ("AutoGen", "AI/机器学习"), ("CrewAI", "AI/机器学习"),
    ("Dify", "AI/机器学习"), ("Flowise", "AI/机器学习"),
    ("Ollama", "AI/机器学习"), ("vLLM", "AI/机器学习"), ("llama.cpp", "AI/机器学习"),
    ("GGML", "AI/机器学习"), ("AWQ", "AI/机器学习"), ("GPTQ", "AI/机器学习"),
    ("LoRA", "AI/机器学习"), ("QLoRA", "AI/机器学习"), ("PEFT", "AI/机器学习"),
    ("RLHF", "AI/机器学习"), ("DPO", "AI/机器学习"), ("PPO", "AI/机器学习"),
    # Data engineering additional
    ("Delta Lake", "数据工程"), ("Apache Iceberg", "数据工程"), ("Apache Hudi", "数据工程"),
    ("Apache Pulsar", "数据工程"), ("Apache NiFi", "数据工程"), ("Apache Beam", "数据工程"),
    ("Apache Storm", "数据工程"), ("Apache Samza", "数据工程"),
    ("Great Expectations", "数据工程"), ("Soda", "数据工程"),
    ("Prefect", "数据工程"), ("Dagster", "数据工程"), ("Mage", "数据工程"),
    ("Kestra", "数据工程"), ("Temporal", "数据工程"),
    ("Redpanda", "数据工程"), ("Conduktor", "数据工程"),
    ("Debezium", "数据工程"), ("CDC", "数据工程"),
    ("Dataform", "数据工程"), ("Looker", "数据工程"),
    ("Metabase", "数据工程"), ("Apache Superset", "数据工程"),
    ("Grafana", "数据工程"), ("Redash", "数据工程"),
    # Testing
    ("Playwright", "测试"), ("Cypress", "测试"), ("TestCafe", "测试"),
    ("Appium", "测试"), ("Detox", "测试"), ("XCTest", "测试"),
    ("Espresso", "测试"), ("Robot Framework", "测试"), ("Cucumber", "测试"),
    ("Behave", "测试"), ("SpecFlow", "测试"), ("Gherkin", "测试"),
    ("k6", "测试"), ("Gatling", "测试"), ("Locust", "测试"),
    ("Artillery", "测试"), ("Vegeta", "测试"),
    ("SonarQube", "测试"), ("ESLint", "测试"), ("Pylint", "测试"),
    ("Flake8", "测试"), ("Black", "测试"), ("isort", "测试"),
    ("MyPy", "测试"), ("Pyright", "测试"), ("Ruff", "测试"),
    # Security additional
    ("Metasploit", "安全"), ("Cobalt Strike", "安全"), ("Kali Linux", "安全"),
    ("John the Ripper", "安全"), ("Hashcat", "安全"), ("Aircrack-ng", "安全"),
    ("Nessus", "安全"), ("Qualys", "安全"), ("Rapid7", "安全"),
    ("CrowdStrike", "安全"), ("SentinelOne", "安全"),
    ("YARA", "安全"), ("Sigma Rules", "安全"), ("MITRE ATT&CK", "安全"),
    ("Splunk SOAR", "安全"), ("Phantom", "安全"),
    ("PKI", "安全"), ("X.509", "安全"), ("TLS", "安全"),
    ("OAuth", "安全"), ("SAML", "安全"), ("OIDC", "安全"),
    ("Zero Trust", "安全"), ("SASE", "安全"),
    # Design additional
    ("InVision", "设计"), ("Zeplin", "设计"), ("Abstract", "设计"),
    ("Principle", "设计"), ("Framer", "设计"), ("Webflow", "设计"),
    ("Canva", "设计"), ("Blender", "设计"), ("After Effects", "设计"),
    ("Premiere Pro", "设计"), ("Final Cut Pro", "设计"),
    ("Cinema 4D", "设计"), ("Maya", "设计"), ("3ds Max", "设计"),
    ("Substance Painter", "设计"), ("Substance Designer", "设计"),
    # Project management additional
    ("Confluence", "项目管理"), ("Notion", "项目管理"), ("Asana", "项目管理"),
    ("Monday.com", "项目管理"), ("Trello", "项目管理"),
    ("Linear", "项目管理"), ("Shortcut", "项目管理"),
    ("OKR", "项目管理"), ("KPI Framework", "项目管理"),
    ("Design Thinking", "项目管理"), ("Lean Startup", "项目管理"),
    ("Value Proposition Canvas", "项目管理"),
    ("Business Model Canvas", "项目管理"),
    # Embedded/IoT additional
    ("Zephyr", "后端开发"), ("FreeRTOS", "后端开发"), ("Mbed", "后端开发"),
    ("Arduino", "后端开发"), ("Raspberry Pi", "后端开发"), ("ESP32", "后端开发"),
    ("LoRa", "后端开发"), ("MQTT", "后端开发"), ("CoAP", "后端开发"),
    ("Zigbee", "后端开发"), ("BLE", "后端开发"), ("NFC", "后端开发"),
    ("CAN Bus", "后端开发"), ("SPI", "后端开发"), ("I2C", "后端开发"),
    ("UART", "后端开发"), ("USB", "后端开发"), ("JTAG", "后端开发"),
    # Blockchain additional
    ("Solana", "后端开发"), ("Polkadot", "后端开发"), ("Cosmos", "后端开发"),
    ("Avalanche", "后端开发"), ("Polygon", "后端开发"), ("Arbitrum", "后端开发"),
    ("Optimism", "后端开发"), ("Base", "后端开发"), ("Hardhat", "后端开发"),
    ("Truffle", "后端开发"), ("Foundry", "后端开发"), ("Anchor", "后端开发"),
    # Game dev additional
    ("Godot", "AI/机器学习"), ("CryEngine", "AI/机器学习"),
    ("Cocos2d", "AI/机器学习"), ("LibGDX", "AI/机器学习"),
    ("FMOD", "AI/机器学习"), ("Wwise", "AI/机器学习"),
    ("Havok", "AI/机器学习"), ("PhysX", "AI/机器学习"),
    ("Photon", "AI/机器学习"), ("Mirror", "AI/机器学习"),
    ("PlayFab", "AI/机器学习"), ("Steamworks", "AI/机器学习"),
    # Mobile additional
    ("SwiftUI", "移动开发"), ("Combine", "移动开发"), ("RxSwift", "移动开发"),
    ("Alamofire", "移动开发"), ("Kingfisher", "移动开发"),
    ("Hilt", "移动开发"), ("Dagger", "移动开发"), ("Koin", "移动开发"),
    ("Coroutines", "移动开发"), ("Flow", "移动开发"),
    ("WorkManager", "移动开发"), ("Navigation Component", "移动开发"),
    ("Compose Multiplatform", "移动开发"), ("KMM", "移动开发"),
    ("Expo", "移动开发"), ("Capacitor", "移动开发"), ("Ionic", "移动开发"),
]


async def main():
    async with AsyncGraphDatabase.driver("bolt://neo4j:7687", auth=("neo4j", "starmap123456")) as driver:
        await driver.verify_connectivity()
        added = 0
        async with driver.session() as ns:
            for skill, area in EXTRA_SKILLS:
                await ns.run("MERGE (s:Skill {name: $n}) SET s.category = $c, s.source = 'esco_extra'", n=skill, c=area)
                await ns.run("MERGE (k:KnowledgeArea {name: $a}) MERGE (s:Skill {name: $n}) MERGE (s)-[:BELONGS_TO]->(k)", a=area, n=skill)
                added += 1

            result = await ns.run("MATCH (s:Skill) RETURN count(s) AS cnt")
            total = (await result.single())["cnt"]
            result = await ns.run("MATCH (n) RETURN count(n) AS cnt")
            all_nodes = (await result.single())["cnt"]
            result = await ns.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
            all_rels = (await result.single())["cnt"]

        print(f"Added {added} skills")
        print(f"Total skills: {total}")
        print(f"Total nodes: {all_nodes}")
        print(f"Total relationships: {all_rels}")

if __name__ == "__main__":
    asyncio.run(main())