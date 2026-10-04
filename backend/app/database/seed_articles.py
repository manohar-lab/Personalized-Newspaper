import asyncio
import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database.session import AsyncSessionLocal
from app.models.article import Article
from app.models.topic import Topic
from app.core.logging import logger

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def compute_content_hash(title: str, content: str) -> str:
    payload = f"{title}:{content}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

DEMO_ARTICLES: List[Dict[str, Any]] = [
    {
        "title": "[DEMO] Breakthrough in Sparse Transformer Architectures Reduces Inference Latency by 40%",
        "slug": "demo-breakthrough-in-sparse-transformer-architectures",
        "description": "DEMO RESEARCH ARTICLE — Engineers showcase a novel dynamic routing attention mechanism that slashes compute overhead in massive language models without quality degradation.",
        "content": """### Editorial Abstract [DEVELOPMENT / DEMO CONTENT]

Recent breakthroughs in neural network efficiency have opened new avenues for real-time model deployment. In this demonstration study, researchers introduce **Sparse-Routing Attention (SRA)**, an algorithmic modification to standard multi-head self-attention that selectively activates only the most salient feed-forward clusters during token generation.

> "By pruning redundant spatial representations at the intermediate tensor level, we achieve a 42% reduction in memory bandwidth and a 38% decrease in time-to-first-token across 70B parameter models."
> — *Dr. Sarah Chen, Principal AI Researcher (Demo)*

#### Key Architectural Findings
1. **Dynamic Sparsity Gating**: Traditional sparse transformers rely on static block sparsity. SRA evaluates activation norms on the fly, dynamically pruning query-key pairs with less than 0.05 relevance weight.
2. **Quantization Resilience**: Unlike prior compression techniques that suffer from FP8 accuracy drift, SRA maintains perplexity parity with full FP16 baselines on standard reasoning benchmarks (GSM8k, HumanEval).
3. **Hardware-Aware Kernel Implementation**: Custom Triton kernels maximize GPU tensor core utilization, bypassing standard CUDA memory coalescing bottlenecks.

```python
# Conceptual SRA Token Gating Kernel Demo
def dynamic_sparse_routing(query, key, threshold=0.05):
    raw_scores = (query @ key.transpose(-2, -1)) * (1.0 / (query.shape[-1] ** 0.5))
    mask = raw_scores > threshold
    return raw_scores.masked_fill(~mask, float("-inf"))
```

#### Industry Impact & Future Outlook
The implications for edge computing and developer tooling are substantial. Real-time code completion models that previously required dedicated server clusters can now comfortably run on enterprise workstations with under 24GB VRAM.

*Disclaimer: This is simulated development/demo content created for testing the Personalized Newspaper application.*""",
        "source_name": "AI Frontier Journal [DEMO]",
        "source_url": "https://example.com/demo/ai-sparse-transformers",
        "author": "Dr. Sarah Chen",
        "image_url": "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 5,
        "status": "PUBLISHED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["artificial-intelligence", "machine-learning", "programming"],
        "days_ago": 0,
        "hours_ago": 2,
    },
    {
        "title": "[DEMO] Next-Generation Asynchronous Systems in Modern Distributed Computing",
        "slug": "demo-next-gen-async-systems-distributed-computing",
        "description": "DEMO TECHNICAL ESSAY — How high-concurrency microservices are shifting from thread-per-request architectures to event-driven lockless actor patterns.",
        "content": """### Architectural Shift in Cloud Infrastructure [DEMO]

Distributed systems engineering is experiencing a major architectural pivot. As traffic volume across globally distributed APIs grows exponentially, traditional synchronization primitives—mutexes, distributed locks, and database transaction queues—are creating unmanageable tail latency.

#### The Problem with Traditional Concurrency
In high-throughput environments (exceeding 100k requests/second), lock contention often consumes up to 60% of CPU cycles. Context switching between OS threads induces cache line invalidations and high memory footprint.

```
[Request Stream] -> [Lock-Free Event Ring Buffer] -> [Isolated Single-Thread Worker] -> [Direct Storage Flush]
```

#### The Lockless Actor Approach
Modern systems are moving towards single-threaded asynchronous execution engines per CPU core, communicating exclusively via message passing across cache-aligned ring buffers.

- **Zero Serialization Latency**: Messages stay in contiguous ring buffers.
- **Deterministic Resource Scheduling**: Fair queuing prevents high-priority starvation.
- **Resilient Partition Tolerance**: Node failures trigger instant failover without holding blocked locks.

*Note: This article is demonstration test data for Personalized Newspaper.*""",
        "source_name": "Cloud Systems Review [DEMO]",
        "source_url": "https://example.com/demo/next-gen-async-systems",
        "author": "Marcus Vance",
        "image_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 6,
        "status": "PUBLISHED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["software-engineering", "cloud-computing", "programming"],
        "days_ago": 0,
        "hours_ago": 5,
    },
    {
        "title": "[DEMO] Early-Stage Tech Venture Funding Trends: Focus Shifts to DeepTech and Vertical AI",
        "slug": "demo-early-stage-tech-venture-funding-trends",
        "description": "DEMO MARKET ANALYSIS — Venture capital allocations in 2026 demonstrate strong investor appetite for sovereign infrastructure, semiconductor startups, and specialized vertical agents.",
        "content": """### Market Overview & Venture Dynamics [DEMO]

Seed and Series A funding across global technology hubs has shifted markedly. While generic consumer applications have seen subdued interest, deep technology startups tackling materials science, sovereign cloud infrastructure, and vertical AI solutions for legal and biomedical engineering have seen robust term sheets.

#### Investment Highlights:
- **Vertical Specialization**: Startups targeting niche enterprise workflows show 3x higher retention rates than general-purpose tools.
- **Cap Table Discipline**: Founders are prioritizing non-dilutive grant capital alongside strategic angel syndicates.
- **Path to Free Cash Flow**: Investors demand unit-economic profitability within 18 months of Series A.

*Disclaimer: This is demonstration development content.*""",
        "source_name": "Founders & Capital Dispatch [DEMO]",
        "source_url": "https://example.com/demo/early-stage-tech-venture",
        "author": "Elena Rostova",
        "image_url": "https://images.unsplash.com/photo-1559526324-4b87b5e36e44?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 4,
        "status": "PUBLISHED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["startups", "business", "finance"],
        "days_ago": 1,
        "hours_ago": 1,
    },
    {
        "title": "[DEMO] Zero-Trust Identity Federation in Cloud-Native Kubernetes Clusters",
        "slug": "demo-zero-trust-identity-federation-kubernetes",
        "description": "DEMO SECURITY BRIEF — Eliminating long-lived API secrets with SPIFFE/SPIRE workload identities and cryptographic mutual TLS.",
        "content": """### Modernizing Workload Security [DEMO]

Static tokens and long-lived AWS IAM secret keys stored in Kubernetes ConfigMaps represent one of the most common vectors in cloud data breaches. The adoption of Zero-Trust workload identity federation is rapidly becoming standard best practice.

#### The Core Tenets of SPIFFE Workload Attestation
1. **Cryptographic Provenance**: Every pod is assigned a short-lived X.509 SVID (SPIFFE Verifiable Identity Document) valid for only 60 minutes.
2. **Dynamic Rotation**: In-memory sidecars renew certificates without requiring container restarts.
3. **Mutual TLS Everywhere**: All inter-service gRPC calls authenticate both client and server identity at the transport layer.

*Disclaimer: Development seed article.*""",
        "source_name": "Cyber Defense Quarterly [DEMO]",
        "source_url": "https://example.com/demo/zero-trust-kubernetes",
        "author": "Aiden Thorne",
        "image_url": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 5,
        "status": "PUBLISHED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["cybersecurity", "cloud-computing", "software-engineering"],
        "days_ago": 1,
        "hours_ago": 8,
    },
    {
        "title": "[DEMO] Rust in Production: What Enterprise Teams Learned After Rewriting Core Services",
        "slug": "demo-rust-in-production-enterprise-retrospective",
        "description": "DEMO CASE STUDY — Lessons in memory safety, compile-time validation, and concurrency ergonomics from a multi-year migration.",
        "content": """### The Engineering Retrospective [DEMO]

Over the past three years, engineering organizations across finance and telecommunications transitioned performance-critical microservices to Rust. This case retrospective highlights the quantitative outcomes and cultural shifts observed.

#### Key Metrics Achieved:
- **Zero Null-Pointer Panics**: Memory safety guarantees eliminated 94% of P1 production crash incidents.
- **Server Fleet Consolidation**: Microservice memory footprints decreased from 1.2 GB per container in Java to under 38 MB in Rust.
- **Developer Onboarding Curve**: While the borrow checker created a 3-week initial friction period, code reviews became significantly faster due to explicit error handling.

*Note: Demo development content.*""",
        "source_name": "The Code Chronicle [DEMO]",
        "source_url": "https://example.com/demo/rust-enterprise-retrospective",
        "author": "Claire Montgomery",
        "image_url": "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 7,
        "status": "PUBLISHED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["programming", "software-engineering", "technology"],
        "days_ago": 2,
        "hours_ago": 4,
    },
    {
        "title": "[DEMO] Quantum Coherence Times Doubled in Novel Silicon Spin Qubit Experiment",
        "slug": "demo-quantum-coherence-times-silicon-spin-qubit",
        "description": "DEMO SCIENCE REPORT — Experimental physicists achieve millisecond-range coherence in isotopically purified silicon at standard cryogenic temperatures.",
        "content": """### Quantum Computing Breakthrough [DEMO]

Maintaining qubit phase coherence in solid-state quantum processors has long been challenged by environmental electromagnetic noise and nuclear spin interactions. A consortium of university physics laboratories announced a two-fold enhancement in coherence time using isotopically purified Silicon-28 matrices.

#### Significance of the Discovery
- **Scalable CMOS Manufacturing**: Silicon spin qubits can leverage existing semiconductor fabrication cleanrooms.
- **Error Correction Thresholds**: Longer coherence times enable surface code error correction without saturating classical control loops.

*Disclaimer: Simulated scientific news demo.*""",
        "source_name": "Frontiers of Science [DEMO]",
        "source_url": "https://example.com/demo/quantum-silicon-spin",
        "author": "Dr. Julian Sterling",
        "image_url": "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 4,
        "status": "PUBLISHED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["science", "technology"],
        "days_ago": 2,
        "hours_ago": 10,
    },
    {
        "title": "[DEMO] Autonomous Multimodal Agents in Healthcare Diagnostic Pipelines",
        "slug": "demo-autonomous-multimodal-agents-healthcare",
        "description": "DEMO MEDICAL TECH REPORT — Clinical trials show AI-assisted radiology triage systems reduce diagnostic turnaround time by 55% for acute neurological scans.",
        "content": """### Clinical Intelligence Demonstration [DEMO]

Hospitals face mounting pressure with emergency imaging backlogs. Recent clinical pilots pairing multimodal vision-language models with human radiologist oversight demonstrate dramatic workflow acceleration.

#### Clinical Protocol & Safety Architecture
- **Pre-Screening Triage**: Scans flagged with critical abnormalities (e.g. acute intracranial hemorrhage) are automatically bumped to top radiologist priority queues.
- **Explainable Heatmaps**: The system outputs attribution heatmaps showing the exact pixel regions informing its assessment.
- **Physician in the Loop**: Final diagnostic sign-off remains strictly under licensed radiologist control.

*Disclaimer: Demo mock healthcare report.*""",
        "source_name": "Digital Health Review [DEMO]",
        "source_url": "https://example.com/demo/autonomous-agents-healthcare",
        "author": "Dr. Aris Thorne",
        "image_url": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 5,
        "status": "PUBLISHED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["health", "artificial-intelligence", "science"],
        "days_ago": 3,
        "hours_ago": 3,
    },
    {
        "title": "[DEMO] The Future of Open-Source Foundation Models: Decentralized Training Collectives",
        "slug": "demo-open-source-foundation-models-decentralized",
        "description": "DEMO COMMUNITY ESSAY — Open source researchers coordinate distributed pipeline parallelism across disparate global compute clusters.",
        "content": """### Democratizing Massive AI Training [DEMO]

As frontier model training costs escalate, open-source AI consortia are pioneering fault-tolerant peer-to-peer training frameworks that harness heterogeneous compute nodes across universities and research labs globally.

#### Algorithmic Innovations
- **Gradient Compression**: 8-bit adaptive quantization reduces inter-datacenter bandwidth requirements by 80%.
- **Byzantine-Resilient Averaging**: Malicious or corrupted gradient submissions are detected and filtered via majority verification.

*Disclaimer: Demo testing content.*""",
        "source_name": "Open Source Gazette [DEMO]",
        "source_url": "https://example.com/demo/decentralized-training",
        "author": "Maya Lin",
        "image_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 6,
        "status": "PUBLISHED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["artificial-intelligence", "programming", "software-engineering"],
        "days_ago": 3,
        "hours_ago": 7,
    },
    {
        "title": "[DEMO] Product-Led Growth in Developer Tooling: Case Studies of 2026",
        "slug": "demo-product-led-growth-developer-tooling",
        "description": "DEMO B2B SAAS PLAYBOOK — How modern devtools achieve frictionless viral expansion without aggressive outbound sales teams.",
        "content": """### The Developer Experience Flywheel [DEMO]

Developers increasingly reject gated demos and high-pressure sales calls. The most successful developer tools in recent years have grown by providing instant, self-serve utility within seconds of `npm install` or `brew install`.

#### Three Hallmarks of Winning Devtools:
1. **Sub-60-Second Time to Magic**: A working prototype running on localhost immediately.
2. **Transparent Open Documentation**: Deep technical documentation with interactive sandbox playgrounds.
3. **Bottom-Up Enterprise Tiering**: Transparent pricing with zero surprise usage caps.

*Disclaimer: Development mock article.*""",
        "source_name": "SaaS Builder Digest [DEMO]",
        "source_url": "https://example.com/demo/plg-developer-tooling",
        "author": "David Kross",
        "image_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 4,
        "status": "PUBLISHED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["startups", "business", "technology"],
        "days_ago": 4,
        "hours_ago": 2,
    },
    {
        "title": "[DEMO — DRAFT] Experimental Pipeline Architecture for Streaming Audio Synthesis",
        "slug": "demo-experimental-pipeline-audio-synthesis-draft",
        "description": "DEMO DRAFT UNPUBLISHED — Internal technical notes on low-latency audio diffusion pipelines.",
        "content": "DRAFT CONTENT — This internal article is in draft status and must NOT appear in published feeds or newspaper editions.",
        "source_name": "Internal Tech Notes [DEMO]",
        "source_url": "https://example.com/demo/draft-audio",
        "author": "Research Team",
        "image_url": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 3,
        "status": "DRAFT",
        "language": "en",
        "is_full_text_available": False,
        "topic_slugs": ["artificial-intelligence", "technology"],
        "days_ago": 5,
        "hours_ago": 1,
    },
    {
        "title": "[DEMO — ARCHIVED] Historical Overview of Monolithic Web Frameworks (2010-2020)",
        "slug": "demo-historical-overview-monolithic-frameworks-archived",
        "description": "DEMO ARCHIVED — Archived overview of past web development paradigms.",
        "content": "ARCHIVED CONTENT — This article is archived and should NOT appear in standard published newspaper sections.",
        "source_name": "Archive Journal [DEMO]",
        "source_url": "https://example.com/demo/archived-monoliths",
        "author": "Legacy Archive",
        "image_url": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80",
        "reading_time_minutes": 4,
        "status": "ARCHIVED",
        "language": "en",
        "is_full_text_available": True,
        "topic_slugs": ["software-engineering", "programming"],
        "days_ago": 10,
        "hours_ago": 0,
    },
]

async def seed_articles(session: AsyncSession) -> int:
    """
    Idempotent seeding function for demo development articles.
    Associates articles with topics using topic slugs.
    """
    # 1. Fetch all topics for lookup
    stmt_topics = select(Topic)
    result_topics = await session.execute(stmt_topics)
    topic_map = {t.slug: t for t in result_topics.scalars().all()}

    inserted_count = 0
    now = utc_now()

    for item in DEMO_ARTICLES:
        slug = item["slug"]
        stmt = (
            select(Article)
            .options(selectinload(Article.topics))
            .where(Article.slug == slug)
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        pub_time = now - timedelta(days=item.get("days_ago", 0), hours=item.get("hours_ago", 0))
        content_hash = compute_content_hash(item["title"], item.get("content") or "")

        target_topics = [topic_map[slug] for slug in item.get("topic_slugs", []) if slug in topic_map]

        if not existing:
            article = Article(
                title=item["title"],
                slug=slug,
                description=item.get("description"),
                content=item.get("content"),
                source_name=item.get("source_name"),
                source_url=item.get("source_url"),
                author=item.get("author"),
                image_url=item.get("image_url"),
                published_at=pub_time,
                reading_time_minutes=item.get("reading_time_minutes", 3),
                status=item.get("status", "PUBLISHED"),
                content_hash=content_hash,
                language=item.get("language", "en"),
                is_full_text_available=item.get("is_full_text_available", True),
                topics=target_topics,
            )
            session.add(article)
            inserted_count += 1
        else:
            # Update fields to keep seed sync
            existing.title = item["title"]
            existing.description = item.get("description")
            existing.content = item.get("content")
            existing.source_name = item.get("source_name")
            existing.source_url = item.get("source_url")
            existing.author = item.get("author")
            existing.image_url = item.get("image_url")
            existing.status = item.get("status", "PUBLISHED")
            existing.reading_time_minutes = item.get("reading_time_minutes", 3)
            existing.content_hash = content_hash
            existing.topics = target_topics

    if inserted_count > 0:
        await session.commit()
        logger.info(f"Seeded {inserted_count} new demo articles into the database.")
    else:
        await session.commit()
        logger.info("Demo articles verified and synchronized in the database.")

    return inserted_count

async def main():
    async with AsyncSessionLocal() as session:
        count = await seed_articles(session)
        print(f"Article seed complete. Added: {count}")

if __name__ == "__main__":
    asyncio.run(main())
