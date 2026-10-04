import asyncio
from typing import List, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import AsyncSessionLocal
from app.models.topic import Topic
from app.core.logging import logger

INITIAL_TOPICS: List[Dict[str, str]] = [
    {
        "name": "Artificial Intelligence",
        "slug": "artificial-intelligence",
        "description": "AI systems, neural networks, machine intelligence, and LLMs.",
    },
    {
        "name": "Machine Learning",
        "slug": "machine-learning",
        "description": "Statistical learning, deep learning algorithms, models, and data science.",
    },
    {
        "name": "Software Engineering",
        "slug": "software-engineering",
        "description": "Software design patterns, architecture, best practices, and code craftsmanship.",
    },
    {
        "name": "Programming",
        "slug": "programming",
        "description": "Programming languages, frameworks, development tools, and algorithms.",
    },
    {
        "name": "Cloud Computing",
        "slug": "cloud-computing",
        "description": "Cloud infrastructure, AWS, GCP, Azure, serverless, and DevOps.",
    },
    {
        "name": "Cybersecurity",
        "slug": "cybersecurity",
        "description": "Information security, network defense, cryptography, and privacy.",
    },
    {
        "name": "Startups",
        "slug": "startups",
        "description": "Venture capital, tech startups, entrepreneurship, and product launches.",
    },
    {
        "name": "Technology",
        "slug": "technology",
        "description": "General technology news, consumer tech, innovation, and digital trends.",
    },
    {
        "name": "Science",
        "slug": "science",
        "description": "Scientific discoveries, physics, space exploration, and biotechnology.",
    },
    {
        "name": "Business",
        "slug": "business",
        "description": "Corporate news, economics, strategy, markets, and management.",
    },
    {
        "name": "Finance",
        "slug": "finance",
        "description": "Financial markets, investing, banking, fintech, and personal finance.",
    },
    {
        "name": "Education",
        "slug": "education",
        "description": "Learning systems, educational technology, universities, and online courses.",
    },
    {
        "name": "Health",
        "slug": "health",
        "description": "Healthcare, medicine, wellness, digital health, and medical research.",
    },
    {
        "name": "Sports",
        "slug": "sports",
        "description": "Athletics, competitive sports, leagues, and sporting events.",
    },
    {
        "name": "Entertainment",
        "slug": "entertainment",
        "description": "Movies, television, music, gaming, and pop culture.",
    },
    {
        "name": "Politics",
        "slug": "politics",
        "description": "Government policies, elections, public affairs, and legislation.",
    },
    {
        "name": "World News",
        "slug": "world-news",
        "description": "Global developments, international affairs, and world events.",
    },
]

async def seed_topics(session: AsyncSession) -> int:
    """
    Idempotent seeding function for topics.
    Inserts missing topics based on unique slug.
    Returns the number of new topics inserted.
    """
    created_count = 0
    for topic_data in INITIAL_TOPICS:
        result = await session.execute(
            select(Topic).where(Topic.slug == topic_data["slug"])
        )
        existing = result.scalar_one_or_none()
        if not existing:
            new_topic = Topic(
                name=topic_data["name"],
                slug=topic_data["slug"],
                description=topic_data.get("description"),
            )
            session.add(new_topic)
            created_count += 1

    if created_count > 0:
        await session.commit()
        logger.info(f"Seeded {created_count} new topics into the database.")
    else:
        logger.info("All initial topics already exist in the database.")

    return created_count

async def main():
    async with AsyncSessionLocal() as session:
        count = await seed_topics(session)
        print(f"Topic seed complete. Added: {count}")

if __name__ == "__main__":
    asyncio.run(main())
