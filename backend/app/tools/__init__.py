from .chroma_patent_tool import (
    ChromaPatentDocument,
    ChromaPatentTool,
)
from .kipris_tool import (
    KiprisPatentRecord,
    KiprisSearchResult,
    KiprisTool,
)

__all__ = [
    "ChromaPatentDocument",
    "ChromaPatentTool",
    "KiprisPatentRecord",
    "KiprisSearchResult",
    "KiprisTool",
    "PatentRecord",
    "SupabaseVectorMatch",
    "SupabaseVectorTool",
]


def __getattr__(name):
    if name in {"PatentRecord", "SupabaseVectorMatch", "SupabaseVectorTool"}:
        from .supabase_vector import (
            PatentRecord,
            SupabaseVectorMatch,
            SupabaseVectorTool,
        )

        return {
            "PatentRecord": PatentRecord,
            "SupabaseVectorMatch": SupabaseVectorMatch,
            "SupabaseVectorTool": SupabaseVectorTool,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
