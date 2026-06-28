# multimodal/core_integration.py – Enhance CrownStar with multi‑modal understanding
from crownstar_core import CrownStarCore
from .service import get_mm_service

class MultiModalCoreExtension:
    def __init__(self, core: CrownStarCore):
        self.core = core
        self.mm = get_mm_service()
    
    async def answer_with_image(self, query: str, image_data: bytes) -> str:
        """Answer using both text and image context"""
        # Get image caption or embedding
        caption = self.mm.caption_image(image_data)
        # Augment query with visual information
        augmented_query = f"Image description: {caption}\nUser question: {query}"
        return self.core.answer_sync(augmented_query)
    
    async def audio_query(self, audio_data: bytes) -> str:
        """Transcribe audio and answer"""
        trans = self.mm.transcribe_audio(audio_data)
        return self.core.answer_sync(trans["text"])

# Monkey‑patch Core if needed (optional)
def extend_core(core: CrownStarCore):
    core.multimodal = MultiModalCoreExtension(core)
    return core
