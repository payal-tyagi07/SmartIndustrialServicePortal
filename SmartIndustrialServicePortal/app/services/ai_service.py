def complaint_draft(title: str, category: str) -> str:
    """Local, privacy-preserving draft helper; replace with an approved LLM adapter if needed."""
    return (f"Issue reported: {title.strip()}.\n\nLocation: [enter exact location]\n\n"
            "Equipment / serial number: [enter asset details]\n\nObserved symptoms: [enter symptoms]\n\n"
            f"Requested assistance: Please inspect and resolve this {category} issue.")
