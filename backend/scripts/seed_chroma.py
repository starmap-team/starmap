"""ChromaDB skill embedding seeder.

Usage:
    python -m scripts.seed_chroma

Seeds the ChromaDB 'skill_embeddings' collection with embeddings for all
canonical skill names from the normalize module (SKILL_ALIAS dict + YAML merge).

This script must be run before vector-based normalization (Step 2 of the
3-step pipeline: alias -> vector -> source count) can function.

Environment variables (optional):
    CHROMA_HOST: ChromaDB server host (default: localhost)
    CHROMA_PORT: ChromaDB server port (default: 8000)
    COLLECTION_NAME: ChromaDB collection name (default: skill_embeddings)
"""

import argparse
import os
import sys

# Add backend root to sys.path so app imports work when run as script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loguru import logger


COLLECTION_NAME = os.getenv("COLLECTION_NAME", "skill_embeddings")
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
BATCH_SIZE = 32


def get_skills() -> list[dict[str, str]]:
    """Load all canonical skill names from the normalize module.

    Returns list of dicts with 'name' key (canonical skill name).
    Each can be extended with 'category' or 'domain' metadata.
    """
    from app.core.extraction.normalize import SKILL_ALIAS, get_standard_skill_seeds

    seeds = get_standard_skill_seeds()
    logger.info("Loaded {} canonical skill names from normalize module", len(seeds))
    return [{"name": name} for name in seeds]


def get_or_create_collection(chroma_client, name: str):
    """Get existing collection or create a new one."""
    try:
        collection = chroma_client.get_collection(name)
        count = collection.count()
        logger.info("Collection '{}' exists with {} documents", name, count)
        return collection
    except Exception:
        logger.info("Creating new collection '{}'", name)
        return chroma_client.create_collection(name)


def embed_skills_batch(
    model, skills: list[dict[str, str]]
) -> tuple[list[str], list[list[float]], list[dict[str, str]]]:
    """Embed a batch of skill names and return (ids, embeddings, metadatas)."""
    names = [s["name"] for s in skills]
    embeddings = model.encode(names, normalize_embeddings=True).tolist()
    ids = [f"skill_{hash(s['name'])}" for s in skills]
    # Normalise hash to positive for valid ChromaDB IDs
    ids = [str(abs(hash(s["name"]))) for s in skills]
    metadatas = [{"standard_name": s["name"]} for s in skills]
    return ids, embeddings, metadatas


def main():
    parser = argparse.ArgumentParser(description="Seed ChromaDB with skill embeddings")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and recreate the collection before seeding",
    )
    parser.add_argument(
        "--model",
        default="BAAI/bge-m3",
        help="SentenceTransformer model name (default: BAAI/bge-m3)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device for model inference (default: cpu)",
    )
    args = parser.parse_args()

    # 1. Load skills
    logger.info("Loading canonical skills...")
    skills = get_skills()
    if not skills:
        logger.error("No skills loaded, aborting")
        sys.exit(1)
    logger.info("Loaded {} skills to embed", len(skills))

    # 2. Connect ChromaDB
    logger.info("Connecting to ChromaDB at {}:{}...", CHROMA_HOST, CHROMA_PORT)
    try:
        import chromadb
    except ImportError:
        logger.error("chromadb not installed. Run: pip install chromadb")
        sys.exit(1)

    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    chroma_client.heartbeat()
    logger.info("ChromaDB connected successfully")

    # 3. Prepare collection
    if args.reset:
        try:
            chroma_client.delete_collection(COLLECTION_NAME)
            logger.info("Deleted existing collection '{}'", COLLECTION_NAME)
        except Exception:
            pass

    collection = get_or_create_collection(chroma_client, COLLECTION_NAME)
    existing_count = collection.count()
    if existing_count > 0 and not args.reset:
        logger.info(
            "Collection already has {} documents. Use --reset to re-seed.",
            existing_count,
        )
        return

    # 4. Load embedding model
    logger.info("Loading SentenceTransformer model '{}' on {}...", args.model, args.device)
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
        sys.exit(1)

    model = SentenceTransformer(args.model, device=args.device)
    logger.info("Model loaded: {}", args.model)

    # 5. Embed and insert in batches
    total = len(skills)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = skills[start:end]
        ids, embeddings, metadatas = embed_skills_batch(model, batch)
        collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas)
        logger.info("  Seeded {}/{} skills...", end, total)

    final_count = collection.count()
    logger.info(
        "Seeding complete: {} skills embedded into collection '{}'",
        final_count,
        COLLECTION_NAME,
    )
    print(f"\nSummary:")
    print(f"  Collection: {COLLECTION_NAME}")
    print(f"  Model:      {args.model}")
    print(f"  Skills:     {final_count}")
    print(f"  ChromaDB:   {CHROMA_HOST}:{CHROMA_PORT}")
    print("\nVector normalization (Step 2) is now ready.")


if __name__ == "__main__":
    main()
