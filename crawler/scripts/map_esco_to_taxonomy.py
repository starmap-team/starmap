#!/usr/bin/env python3
"""将 ESCO IT 技能映射到 StarMap 198 技能本体"""
import csv
import os
import yaml

ESCO_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "ontology", "esco_it_skills.csv")
TAXONOMY_YAML = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "ontology", "skill_taxonomy.yaml")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "ontology", "esco_mapping.yaml")

# ESCO 技能 → StarMap 技能的映射规则
# 格式: {ESCO preferredLabel (小写): StarMap skill name}
MAPPING_RULES = {
    # 编程语言
    "c++": "C++",
    "c++ programming": "C++",
    "c# programming": "C#",
    "java programming": "Java",
    "python programming": "Python",
    "javascript programming": "JavaScript",
    "typescript programming": "TypeScript",
    "ruby programming": "Ruby",
    "php programming": "PHP",
    "swift programming": "Swift",
    "kotlin programming": "Kotlin",
    "scala programming": "Scala",
    "go programming": "Go",
    "rust programming": "Rust",
    "r programming": "R",
    "matlab": "MATLAB",
    "haskell": "Haskell",
    "perl programming": "Perl",
    "lua programming": "Lua",
    "objective-c": "Objective-C",
    "dart programming": "Dart",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "scss": "SCSS",
    "sass": "Sass",

    # 数据库
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "oracle database": "Oracle",
    "sql server": "SQL Server",
    "database management": "Database Design",
    "database design": "Database Design",
    "nosql": "NoSQL",
    "data modeling": "Data Modeling",
    "db2": "DB2",

    # Web 开发框架
    "react": "React",
    "angular": "Angular",
    "vue.js": "Vue.js",
    "vue js": "Vue.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "django": "Django",
    "flask": "Flask",
    "spring boot": "Spring Boot",
    "spring framework": "Spring Framework",
    "express.js": "Express.js",
    "fastapi": "FastAPI",
    "laravel": "Laravel",
    "ruby on rails": "Ruby on Rails",
    "rails": "Ruby on Rails",
    "asp.net": "ASP.NET",
    "dotnet": ".NET",
    ".net framework": ".NET",
    "jquery": "jQuery",
    "bootstrap": "Bootstrap",
    "webpack": "Webpack",
    "next.js": "Next.js",
    "nuxt.js": "Nuxt.js",
    "svelte": "Svelte",
    "ember.js": "Ember.js",
    "backbone.js": "Backbone.js",

    # 云计算/DevOps
    "aws": "AWS",
    "amazon web services": "AWS",
    "microsoft azure": "Azure",
    "azure": "Azure",
    "google cloud platform": "GCP",
    "gcp": "GCP",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "ci/cd": "CI/CD",
    "continuous integration": "CI/CD",
    "continuous deployment": "CI/CD",
    "devops": "DevOps",
    "cloud computing": "Cloud Computing",
    "cloud architecture": "Cloud Architecture",
    "serverless computing": "Serverless",
    "infrastructure as code": "Infrastructure as Code",
    "linux administration": "Linux",
    "windows server": "Windows Server",
    "unix": "Unix",
    "bash scripting": "Shell",
    "powershell": "PowerShell",

    # 数据科学/AI/ML
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "artificial intelligence": "Artificial Intelligence",
    "data science": "Data Science",
    "data analysis": "Data Analysis",
    "data mining": "Data Mining",
    "natural language processing": "NLP",
    "nlp": "NLP",
    "computer vision": "Computer Vision",
    "neural networks": "Neural Networks",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "keras": "Keras",
    "scikit-learn": "Scikit-learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scipy": "SciPy",
    "matplotlib": "Matplotlib",
    "seaborn": "Seaborn",
    "big data": "Big Data",
    "hadoop": "Hadoop",
    "spark": "Spark",
    "kafka": "Kafka",
    "etl": "ETL",
    "data warehousing": "Data Warehousing",
    "business intelligence": "Business Intelligence",
    "data visualization": "Data Visualization",
    "tableau": "Tableau",
    "power bi": "Power BI",
    "predictive analytics": "Predictive Analytics",
    "statistical modeling": "Statistical Modeling",
    "time series analysis": "Time Series Analysis",

    # 网络/安全
    "cybersecurity": "Cybersecurity",
    "information security": "Information Security",
    "network security": "Network Security",
    "penetration testing": "Penetration Testing",
    "ethical hacking": "Ethical Hacking",
    "firewall management": "Firewall",
    "encryption": "Encryption",
    "cryptography": "Cryptography",
    "vpn configuration": "VPN",
    "intrusion detection": "Intrusion Detection",
    "security auditing": "Security Auditing",
    "vulnerability assessment": "Vulnerability Assessment",
    "incident response": "Incident Response",
    "digital forensics": "Digital Forensics",

    # 软件工程
    "software development": "Software Development",
    "software engineering": "Software Engineering",
    "object-oriented programming": "Object-Oriented Programming",
    "design patterns": "Design Patterns",
    "api design": "API Design",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "system design": "System Design",
    "version control": "Version Control",
    "git": "Git",
    "github": "GitHub",
    "code review": "Code Review",
    "unit testing": "Unit Testing",
    "integration testing": "Integration Testing",
    "test driven development": "TDD",
    "tdd": "TDD",
    "agile methodology": "Agile",
    "scrum": "Scrum",
    "kanban": "Kanban",
    "jira": "JIRA",
    "confluence": "Confluence",

    # 前端/UI
    "frontend development": "Frontend Development",
    "front-end development": "Frontend Development",
    "user interface design": "UI Design",
    "ui development": "UI Development",
    "ux design": "UX Design",
    "responsive design": "Responsive Design",
    "web development": "Web Development",
    "web design": "Web Design",
    "cross-browser compatibility": "Cross-browser Compatibility",
    "accessibility": "Accessibility",

    # 移动开发
    "mobile app development": "Mobile Development",
    "android development": "Android Development",
    "ios development": "iOS Development",
    "react native": "React Native",
    "flutter": "Flutter",
    "xamarin": "Xamarin",
    "ionic": "Ionic",
    "mobile development": "Mobile Development",

    # 系统/运维
    "system administration": "System Administration",
    "sysadmin": "System Administration",
    "it support": "IT Support",
    "technical support": "Technical Support",
    "network administration": "Network Administration",
    "system monitoring": "System Monitoring",
    "log management": "Log Management",
    "performance tuning": "Performance Tuning",
    "load balancing": "Load Balancing",
    "reverse proxy": "Reverse Proxy",

    # 架构
    "software architecture": "Software Architecture",
    "solution architecture": "Solution Architecture",
    "enterprise architecture": "Enterprise Architecture",
    "microservices": "Microservices",
    "monolithic architecture": "Monolithic Architecture",
    "event-driven architecture": "Event-driven Architecture",
    "domain-driven design": "Domain-Driven Design",
    "ddd": "Domain-Driven Design",
    "clean architecture": "Clean Architecture",
    "hexagonal architecture": "Hexagonal Architecture",

    # 其他技术
    "blockchain": "Blockchain",
    "smart contracts": "Smart Contracts",
    "seo": "SEO",
    "technical writing": "Technical Writing",
    "documentation": "Documentation",
    "api documentation": "API Documentation",
    "agile project management": "Agile Project Management",
    "scrum master": "Scrum Master",
    "product owner": "Product Owner",
    "technical lead": "Technical Lead",
    "tech lead": "Technical Lead",
    "full stack development": "Full Stack Development",
    "fullstack": "Full Stack Development",
    "backend development": "Backend Development",
    "back-end development": "Backend Development",
    "frontend development": "Frontend Development",
    "site reliability engineering": "SRE",
    "sre": "SRE",
    "platform engineering": "Platform Engineering",
    "embedded systems": "Embedded Systems",
    "firmware development": "Firmware",
    "iot": "IoT",
    "internet of things": "IoT",
    "robotics": "Robotics",
    "automation": "Automation",
    "rpa": "RPA",
    "low-code development": "Low-code",
    "cloud migration": "Cloud Migration",
    "digital transformation": "Digital Transformation",
    "signal processing": "Signal Processing",
    "computer engineering": "Computer Engineering",
    "statistics": "Statistics",
    "physics": "Physics",
    "biotechnology": "Biotechnology",
    "nuclear energy": "Nuclear Energy",
    "robotics": "Robotics",
    "automation technology": "Automation",
    "computer vision": "Computer Vision",
    "principles of artificial intelligence": "Artificial Intelligence",
    "deep learning": "Deep Learning",
    "machine learning": "Machine Learning",
    "natural language processing": "NLP",
    "internet of things": "IoT",
    "blockchain": "Blockchain",
    "cloud technologies": "Cloud Computing",
    "devops": "DevOps",
    "penetration testing tool": "Penetration Testing",
    "ict encryption": "Encryption",
    "use object-oriented programming": "Object-Oriented Programming",
    "query languages": "SQL",
    "style sheet languages": "CSS",
    "use markup languages": "HTML",
    "database management systems": "Database Design",
    "integrated development environment software": "IDE",
    "graphics editor software": "UI Design",
    "software ui design patterns": "Design Patterns",
    "software architecture models": "Software Architecture",
    "use software design patterns": "Design Patterns",
    "data extraction, transformation and loading tools": "ETL",
    "perform data analysis": "Data Analysis",
    "perform data mining": "Data Mining",
    "analyse big data": "Big Data",
    "utilise machine learning": "Machine Learning",
    "conduct ict code review": "Code Review",
    "perform software unit testing": "Unit Testing",
    "execute integration testing": "Integration Testing",
    "tools for software configuration management": "Version Control",
    "tools for ict test automation": "Testing",
    "ict project management methodologies": "Project Management",
    "implement a firewall": "Firewall",
    "perform ict security testing": "Security Testing",
    "apply information security policies": "Information Security",
    "manage system security": "Security",
    "ict network security risks": "Network Security",
    "design database in the cloud": "Cloud Architecture",
    "implement data warehousing techniques": "Data Warehousing",
    "use specific data analysis software": "Data Analysis",
    "design cloud architecture": "Cloud Architecture",
    "develop information security strategy": "Information Security",
    "ensure information security": "Information Security",
    "plan migration to cloud": "Cloud Migration",
    "automate cloud tasks": "Cloud Computing",
    "cloud monitoring and reporting": "Cloud Computing",
    "maintain responsive design": "Responsive Design",
    "create digital files": "Digital Literacy",
    "operate digital hardware": "Digital Literacy",
    "digital data processing": "Data Processing",
    "store digital data and systems": "Data Storage",
    "manage digital documents": "Documentation",
    "manage digital archives": "Data Storage",
    "browse, search and filter data, information and digital content": "Data Analysis",
    "manage data, information and digital content": "Data Management",
    "use communication and collaboration software": "Collaboration Tools",
    "use presentation software": "Presentation Tools",
    "use spreadsheets software": "Spreadsheet",
    "use online tools to collaborate": "Collaboration Tools",
    "problem-solving with digital tools": "Problem Solving",
    "protect personal data and privacy": "Data Privacy",
    "safeguard online privacy and identity": "Data Privacy",
    "apply digital security measures": "Security",
    "protect the health of others": "Ergonomics",
    "keep up with digital transformation of industrial processes": "Digital Transformation",
    "creatively use digital technologies": "Digital Literacy",
    "collaborate through digital technologies": "Collaboration Tools",
    "share through digital technologies": "Collaboration Tools",
    "interact through digital technologies": "Digital Literacy",
    "evaluate data, information and digital content": "Data Analysis",
    "integrate and re-elaborate digital content": "Data Processing",
    "develop digital content": "Content Creation",
    "digital content creation": "Content Creation",
    "create digital images": "Graphic Design",
    "edit digital moving images": "Video Editing",
    "digital compositing": "Video Editing",
    "use digital illustration techniques": "Graphic Design",
    "lay out digital written content": "Content Creation",
    "design digital call to action": "UX Design",
    "plan digital marketing": "Digital Marketing",
    "plan social media marketing campaigns": "Social Media Marketing",
    "digital marketing techniques": "Digital Marketing",
    "teach digital literacy": "Digital Literacy",
    "engage in citizenship through digital technologies": "Digital Literacy",
    "identify digital competence gaps": "Digital Literacy",
    "protect the environment from the impact of the digital technologies": "Sustainability",
    "protect health and well-being while using digital technologies": "Ergonomics",
    "copyright and licenses related to digital content": "Copyright",
    "manage digital identity": "Digital Identity",
    "types of digital badges": "Digital Literacy",
    "develop translation memory software": "Translation Tools",
    "perform online data analysis": "Data Analysis",
    "keywords in digital content": "SEO",
    "use markup languages": "HTML",
    "maintain system logs": "Log Management",
    "provide user documentation": "Documentation",
    "provide technical documentation": "Documentation",
    "set up documentation control system": "Documentation",
    "utilise computer-aided software engineering tools": "IDE",
    "write database documentation": "Documentation",
    "conduct ict code review": "Code Review",
    "provide software testing documentation": "Testing",
    "define software architecture": "Software Architecture",
    "design enterprise architecture": "Enterprise Architecture",
    "perform safety data analysis": "Data Analysis",
    "use methods of logistical data analysis": "Data Analysis",
    "analyse large-scale data in healthcare": "Big Data",
    "analyse data for aeronautical publications": "Data Analysis",
    "analyse oil operations data": "Data Analysis",
    "process collected survey data": "Data Analysis",
    "perform calorimeter operation": "Data Analysis",
    "use specific data analysis software": "Data Analysis",
    "apply digital mapping": "GIS",
    "develop strategies for accessibility": "Accessibility",
    "test system accessibility for users with special needs": "Accessibility",
    "ict accessibility standards": "Accessibility",
    "call-centre technologies": "Telecommunications",
    "integrated circuit types": "Electronics",
    "signal processing": "Signal Processing",
    "design optical systems": "Optics",
    "design electronic systems": "Electronics",
    "design electrical systems": "Electrical Engineering",
    "design electromechanical systems": "Electrical Engineering",
    "install automation components": "Automation",
    "design automation components": "Automation",
    "test electronic units": "Electronics",
    "test mechatronic units": "Mechatronics",
    "teach electronics and automation principles": "Electronics",
    "install electrical and electronic equipment": "Electronics",
    "install electrical mining machinery": "Electronics",
    "operate signal generator": "Electronics",
    "program lift controller": "Automation",
    "computer engineering": "Computer Engineering",
    "design sprinkler systems": "Building Automation",
    "building automation": "Building Automation",
    "ensure infrastructure accessibility": "Accessibility",
}


def load_esco_skills():
    """加载 ESCO IT 技能"""
    skills = []
    with open(ESCO_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            skills.append(row)
    return skills


def load_taxonomy():
    """加载 StarMap 技能本体（手动解析特殊 YAML 结构）"""
    skills = []
    with open(TAXONOMY_YAML, "r", encoding="utf-8") as f:
        content = f.read()

    # 手动提取所有 skill name
    import re
    # 匹配 "- name: "XXX"" 模式
    pattern = r'- name: "([^"]+)"'
    matches = re.findall(pattern, content)
    for name in matches:
        skills.append(name)

    return skills


def create_mapping(esco_skills, taxonomy):
    """创建 ESCO → StarMap 映射"""
    mapping = {}
    matched = 0
    unmatched = []

    for skill in esco_skills:
        label = skill.get("PREFERREDLABEL", "").lower().strip()
        if label in MAPPING_RULES:
            starmap_skill = MAPPING_RULES[label]
            mapping[label] = {
                "esco_label": skill.get("PREFERREDLABEL", ""),
                "esco_uri": skill.get("ORIGINURI", ""),
                "starmap_skill": starmap_skill,
                "description": skill.get("DESCRIPTION", "")[:100],
            }
            matched += 1
        else:
            unmatched.append(label)

    return mapping, matched, unmatched


def main():
    print("加载 ESCO IT 技能...")
    esco_skills = load_esco_skills()
    print(f"ESCO IT 技能数: {len(esco_skills)}")

    print("加载 StarMap 技能本体...")
    taxonomy_skills = load_taxonomy()
    print(f"StarMap 技能数: {len(taxonomy_skills)}")

    print("创建映射...")
    mapping, matched, unmatched = create_mapping(esco_skills, None)
    print(f"匹配成功: {matched}")
    print(f"未匹配: {len(unmatched)}")

    # 保存映射
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "version": "1.0",
                "description": "ESCO → StarMap 技能映射",
                "total_esco_skills": len(esco_skills),
                "total_mapped": matched,
                "mappings": mapping,
            },
            f,
            allow_unicode=True,
            default_flow_style=False,
        )

    print(f"\n已保存到: {OUTPUT_PATH}")

    # 显示部分映射
    print("\n部分映射示例:")
    for i, (esco, info) in enumerate(list(mapping.items())[:20]):
        print(f"  {info['esco_label']} -> {info['starmap_skill']}")

    return mapping


if __name__ == "__main__":
    main()
