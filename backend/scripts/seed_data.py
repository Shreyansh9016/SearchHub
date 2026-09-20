import random
from datetime import datetime, timedelta, timezone

TOPICS = {
    "kafka": ("Kafka", ["consumer groups", "partitions", "offsets", "producers", "brokers",
                        "log compaction", "rebalancing", "exactly-once semantics"],
              ["backend", "microservices"]),
    "redis": ("Redis", ["sorted sets", "pub/sub", "streams", "persistence", "eviction policies",
                        "pipelining", "cluster mode", "lua scripting"],
              ["caching", "backend"]),
    "postgresql": ("PostgreSQL", ["indexes", "query planner", "vacuum", "transactions",
                                  "partitioning", "replication", "connection pooling", "migrations"],
                   ["backend"]),
    "docker": ("Docker", ["multi-stage builds", "volumes", "networking", "image layers",
                          "compose files", "health checks", "registries", "security scanning"],
               ["devops"]),
    "kubernetes": ("Kubernetes", ["pods", "deployments", "ingress", "autoscaling", "operators",
                                  "config maps", "stateful sets", "rolling updates"],
                   ["devops", "microservices"]),
    "python": ("Python", ["asyncio", "generators", "type hints", "decorators", "packaging",
                          "context managers", "dataclasses", "profiling"],
               ["backend"]),
    "javascript": ("JavaScript", ["promises", "closures", "event loop", "modules", "web workers",
                                  "prototypes", "generators", "bundlers"],
                   ["react"]),
    "react": ("React", ["hooks", "memoization", "suspense", "context", "server components",
                        "reconciliation", "refs", "error boundaries"],
              ["javascript"]),
    "rabbitmq": ("RabbitMQ", ["exchanges", "dead letter queues", "acknowledgements", "prefetch",
                              "routing keys", "quorum queues", "retries", "idempotent consumers"],
                 ["backend", "microservices"]),
    "search": ("Search", ["inverted indexes", "BM25 ranking", "tokenization", "autocomplete",
                          "fuzzy matching", "relevance tuning", "stemming", "highlighting"],
               ["algorithms", "backend"]),
    "security": ("Security", ["password hashing", "JWT tokens", "rate limiting", "CSRF protection",
                              "SQL injection", "secrets management", "OAuth flows", "input validation"],
                 ["backend"]),
    "testing": ("Testing", ["unit tests", "integration tests", "mocking", "fixtures",
                            "property-based testing", "test coverage", "flaky tests", "contract tests"],
                ["devops"]),
    "devops": ("DevOps", ["continuous integration", "blue-green deploys", "infrastructure as code",
                          "feature flags", "rollbacks", "secrets rotation", "runbooks", "release trains"],
               ["observability"]),
    "networking": ("Networking", ["TCP handshakes", "DNS resolution", "load balancing", "TLS",
                                  "HTTP/2", "WebSockets", "CDN caching", "connection timeouts"],
                   ["backend"]),
    "algorithms": ("Algorithms", ["binary search", "tries", "edit distance", "hash tables",
                                  "graph traversal", "dynamic programming", "heaps", "sorting"],
                   ["search"]),
    "microservices": ("Microservices", ["service discovery", "sagas", "API gateways",
                                        "event sourcing", "circuit breakers", "idempotency",
                                        "distributed tracing", "eventual consistency"],
                      ["backend", "observability"]),
    "observability": ("Observability", ["structured logging", "metrics", "distributed tracing",
                                        "alerting", "dashboards", "service level objectives",
                                        "sampling", "error budgets"],
                      ["devops"]),
    "caching": ("Caching", ["cache invalidation", "TTL strategies", "write-through caches",
                            "cache stampedes", "CDN caching", "eviction policies",
                            "cache-aside pattern", "hot keys"],
                ["backend", "redis"]),
    "backend": ("Backend", ["REST design", "pagination", "background jobs", "API versioning",
                            "error handling", "idempotent endpoints", "connection pooling",
                            "graceful shutdown"],
                ["microservices"]),
}

TITLE_TEMPLATES = [
    "{T}: {C} Explained",
    "A Practical Guide to {C} in {T}",
    "Understanding {C} in {T}",
    "{T} {C}: Best Practices",
    "Common Pitfalls with {C} in {T}",
    "Scaling {T} with {C}",
    "{C} in {T}: A Deep Dive",
    "Getting Started with {C} in {T}",
]

INTRO = [
    "{C} is one of the most important ideas to understand when working with {T}.",
    "Most teams meet {C} in {T} the hard way, usually during an incident.",
    "This article walks through {C} in {T} with practical, production-minded advice.",
]
BODY = [
    "In {T}, {C} determines how the system behaves under load, so it pays to measure it early.",
    "A common mistake with {C} is to tune it without a benchmark; always compare against a baseline.",
    "When {C} is configured well, {T} becomes noticeably easier to operate and to reason about.",
    "Consider how {C} interacts with {C2}; the two are closely related in real {T} deployments.",
    "Monitoring {C} gives early warning of trouble long before users notice anything wrong.",
    "The default settings for {C} are safe but rarely optimal, so review them for your workload.",
    "Write a small test that exercises {C} so regressions in {T} are caught in continuous integration.",
    "Document the decisions you make about {C}; future maintainers of your {T} setup will thank you.",
]
PASSING = [
    "Some teams also pair this with {OT} {OC}, but that is outside the scope of this article.",
    "For background on {OT} {OC}, see the related material elsewhere in this knowledge base.",
]
TYPO_SENTENCES = [
    "You will recieve better results if you seperate concerns and avoid the occurence of hidden state.",
    "An asynchronus design is definately easier to scale, though the tradeoffs are non-obvious.",
    "Be carefull with configuraton drift; it is a comon cause of surprising behaviour in production.",
    "Both the messaging and cache clients need a sensible timeout, otherwise requests hang indefinately.",
]

ANCHORS = [
    {
        "title": "Kafka Consumer Groups Explained",
        "body": ("A Kafka consumer group is a set of consumers that cooperate to read a topic. "
                 "Each partition is assigned to exactly one consumer in the group, so consumer groups "
                 "give you parallelism and fault tolerance. When a consumer joins or leaves, the group "
                 "rebalances. Understanding consumer group offsets and rebalancing is essential for "
                 "reliable Kafka pipelines. A consumer group tracks its committed offsets independently "
                 "of every other consumer group."),
        "tags": ["kafka", "backend"],
    },
    {
        "title": "Tuning Kafka Consumer Group Rebalances",
        "body": ("Slow rebalances hurt throughput. Tune session timeouts and use static membership so a "
                 "restarting consumer does not trigger a full consumer group rebalance. Cooperative "
                 "rebalancing lets each Kafka consumer keep its partitions during a group change."),
        "tags": ["kafka", "microservices"],
    },
    {
        "title": "Redis Caching Patterns",
        "body": ("Caching with Redis usually follows the cache-aside pattern: read the cache, fall back to "
                 "the database, then populate the cache with a TTL. Invalidate keys on writes to avoid "
                 "stale data. Redis makes caching fast because everything lives in memory."),
        "tags": ["redis", "caching", "backend"],
    },
    {
        "title": "Redis Streams Explained",
        "body": ("Redis Streams are an append-only log inside Redis. Producers append entries, and consumer "
                 "groups read them with acknowledgements. Compared with Kafka they are lighter to operate, "
                 "though retention and scale are more limited."),
        "tags": ["redis", "backend"],
    },
    {
        "title": "Choosing a Message Broker",
        "body": ("Teams often compare RabbitMQ and Kafka. RabbitMQ is a smart broker with per-message "
                 "acknowledgements. Kafka is a distributed log; a consumer group reads it at its own pace."),
        "tags": ["rabbitmq", "kafka", "microservices"],
    },
]


def _make_article(rng, topic, concept, template):
    name, concepts, related = TOPICS[topic]
    c2 = rng.choice([c for c in concepts if c != concept])
    other_topic = rng.choice([t for t in TOPICS if t != topic])
    oname, oconcepts, _ = TOPICS[other_topic]
    fmt = dict(T=name, C=concept, C2=c2, OT=oname, OC=rng.choice(oconcepts))

    paragraphs = [rng.choice(INTRO).format(**fmt)]
    paragraphs += [s.format(**fmt) for s in rng.sample(BODY, k=rng.randint(4, 6))]
    if rng.random() < 0.35:
        paragraphs.insert(rng.randint(1, len(paragraphs)), rng.choice(PASSING).format(**fmt))
    if rng.random() < 0.08:
        paragraphs.append(rng.choice(TYPO_SENTENCES))

    tags = [topic] + [t for t in related if rng.random() < 0.8]
    return {
        "title": template.format(T=name, C=concept),
        "body": "\n\n".join(paragraphs),
        "tags": tags,
    }


def generate_articles(n=520, seed=42, now=None):
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)

    combos = [(t, c, tpl) for t, (_, cs, _) in TOPICS.items() for c in cs for tpl in TITLE_TEMPLATES]
    rng.shuffle(combos)

    n_dupes = max(20, n // 25)
    n_unique = n - len(ANCHORS) - n_dupes
    articles = [dict(a) for a in ANCHORS]
    articles += [_make_article(rng, *combo) for combo in combos[:n_unique]]

    for src in rng.sample(articles[len(ANCHORS):], k=n_dupes):
        suffix = rng.choice([" (Updated)", " - Revisited", " (Part 2)", " [Draft]"])
        extra = " Note: this article supersedes an earlier version."
        articles.append({"title": src["title"] + suffix, "body": src["body"] + extra, "tags": list(src["tags"])})

    for a in articles:
        a["created_at"] = now - timedelta(days=rng.randint(0, 180), hours=rng.randint(0, 23))
    return articles
