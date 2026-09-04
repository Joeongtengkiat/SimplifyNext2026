# Deterministic keyword categorization, not an LLM call -- this runs on every schedule item on
# every state load, and a topic label doesn't need language understanding to get right for the
# vocabulary a student's calendar actually uses. Order matters: first match wins, so more
# specific categories should come before general ones.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "career": ["interview", "internship", "job", "shift", "career", "networking", "resume", "recruiter"],
    "academic": [
        "lecture", "tutorial", "class", "assignment", "exam", "study", "homework",
        "project", "seminar", "quiz", "thesis", "lab", "coursework",
    ],
    "health": ["gym", "basketball", "workout", "run", "swim", "sport", "yoga", "fitness", "training"],
    "social": ["coffee", "hangout", "party", "dinner", "friend", "outing", "catch up", "catchup", "lunch with"],
}
DEFAULT_CATEGORY = "personal"


def categorize(title: str, event_type: str = "") -> str:
    haystack = f"{title} {event_type}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return DEFAULT_CATEGORY
