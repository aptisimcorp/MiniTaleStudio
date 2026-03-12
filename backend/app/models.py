from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ?? Auth Models ??????????????????????????????????????????????????????????

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    user_id: str
    email: str
    role: str = "admin"


# ?? Enums ????????????????????????????????????????????????????????????????

class StoryCategory(str, Enum):
    HORROR = "horror"
    FUNNY = "funny"
    CRIME = "crime"
    THRILLER = "thriller"
    HISTORY = "history"
    MYSTERY = "mystery"
    ADULT = "adult"
    CUSTOM = "custom"


class Language(str, Enum):
    ENGLISH = "english"
    HINDI = "hindi"


class DurationRange(str, Enum):
    SHORT = "60-90"
    MEDIUM = "90-120"
    LONG = "120-180"


class GenerationMode(str, Enum):
    INSTANT = "instant"
    SCHEDULED = "scheduled"


class ScheduleType(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    CRON = "cron"


class ImageStyle(str, Enum):
    LEGO = "lego"
    COMIC_BOOK = "comic_book"
    DISNEY_TOON = "disney_toon"
    STUDIO_GHIBLI = "studio_ghibli"
    PIXELATED = "pixelated"
    CREEPY_TOON = "creepy_toon"
    CHILDRENS_BOOK = "childrens_book"
    PHOTO_REALISM = "photo_realism"
    MINECRAFT = "minecraft"
    WATERCOLOR = "watercolor"
    EXPRESSIONISM = "expressionism"
    CHARCOAL = "charcoal"
    GTAV = "gtav"
    ANIME = "anime"
    FILM_NOIR = "film_noir"
    THREE_D_TOON = "3d_toon"


class SubtitleStyle(str, Enum):
    DEFAULT = "default"
    BOLD = "bold"
    MINIMAL = "minimal"


class AIService(str, Enum):
    OPENAI = "openai"
    GROK = "grok"


class CharacterStyle(str, Enum):
    REALISTIC = "realistic"
    THREE_D_TOON = "3dtoon"
    GHIBLI = "ghibli"
    LEGO = "lego"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStep(str, Enum):
    QUEUED = "queued"
    STORY = "generating_story"
    IMAGES = "generating_images"
    VIDEO_CLIPS = "generating_video_clips"
    NARRATION = "generating_narration"
    SUBTITLES = "generating_subtitles"
    ASSEMBLING = "assembling_video"
    UPLOADING = "uploading_blob"
    YOUTUBE_UPLOAD = "uploading_youtube"
    CLEANUP = "cleanup"
    DONE = "done"


# Step ordering for progress percentage
PIPELINE_STEP_ORDER = [
    PipelineStep.QUEUED,
    PipelineStep.STORY,
    PipelineStep.IMAGES,
    PipelineStep.VIDEO_CLIPS,
    PipelineStep.NARRATION,
    PipelineStep.SUBTITLES,
    PipelineStep.ASSEMBLING,
    PipelineStep.UPLOADING,
    PipelineStep.YOUTUBE_UPLOAD,
    PipelineStep.CLEANUP,
    PipelineStep.DONE,
]

PIPELINE_STEP_LABELS = {
    PipelineStep.QUEUED: "Queued",
    PipelineStep.STORY: "Generating Story",
    PipelineStep.IMAGES: "Generating Images",
    PipelineStep.VIDEO_CLIPS: "Generating Video Clips",
    PipelineStep.NARRATION: "Generating Narration",
    PipelineStep.SUBTITLES: "Generating Subtitles",
    PipelineStep.ASSEMBLING: "Assembling Video",
    PipelineStep.UPLOADING: "Uploading to Cloud",
    PipelineStep.YOUTUBE_UPLOAD: "Uploading to YouTube",
    PipelineStep.CLEANUP: "Cleaning Up",
    PipelineStep.DONE: "Done",
}


# ?? Request / Response Models ????????????????????????????????????????????

class ConfigurationCreate(BaseModel):
    category: StoryCategory = StoryCategory.HORROR
    custom_category: Optional[str] = None
    language: Language = Language.ENGLISH
    duration: DurationRange = DurationRange.SHORT
    generation_mode: GenerationMode = GenerationMode.INSTANT
    schedule_type: Optional[ScheduleType] = None
    cron_expression: Optional[str] = None
    num_videos: int = Field(default=1, ge=1, le=10)
    voice_type: str = "alloy"
    background_music: bool = False
    auto_upload_youtube: bool = False
    subtitle_style: SubtitleStyle = SubtitleStyle.DEFAULT
    image_style: ImageStyle = ImageStyle.PHOTO_REALISM
    watermark_path: Optional[str] = None
    splash_start_path: Optional[str] = None
    splash_end_path: Optional[str] = None
    # Character pipeline
    ai_service: AIService = AIService.OPENAI
    character_style: CharacterStyle = CharacterStyle.REALISTIC
    characters: list[str] = Field(default_factory=list)


class ConfigurationResponse(ConfigurationCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ScheduleCreate(BaseModel):
    configuration_id: str
    schedule_type: ScheduleType
    cron_expression: Optional[str] = None
    enabled: bool = True


class ScheduleResponse(ScheduleCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class JobResponse(BaseModel):
    id: str
    configuration_id: str
    status: JobStatus
    category: str
    language: str
    duration: str
    video_path: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class VideoInfo(BaseModel):
    id: str
    job_id: str
    user_id: Optional[str] = None
    filename: str
    category: str
    language: str
    duration: str
    thumbnail: Optional[str] = None
    file_path: str
    blob_url: Optional[str] = None
    file_size: Optional[int] = None
    created_at: str


class YouTubeUploadRequest(BaseModel):
    video_id: str


class YouTubeUploadResponse(BaseModel):
    youtube_video_id: str
    youtube_url: str


class GenerateVideoRequest(BaseModel):
    configuration_id: Optional[str] = None
    category: StoryCategory = StoryCategory.HORROR
    custom_category: Optional[str] = None
    language: Language = Language.ENGLISH
    duration: DurationRange = DurationRange.SHORT
    voice_type: str = "alloy"
    background_music: bool = False
    auto_upload_youtube: bool = False
    subtitle_style: SubtitleStyle = SubtitleStyle.DEFAULT
    image_style: ImageStyle = ImageStyle.PHOTO_REALISM
    watermark_path: Optional[str] = None
    splash_start_path: Optional[str] = None
    splash_end_path: Optional[str] = None
    # Character pipeline
    ai_service: AIService = AIService.OPENAI
    character_style: CharacterStyle = CharacterStyle.REALISTIC
    characters: list[str] = Field(default_factory=list)


# ?? Pipeline internal models ?????????????????????????????????????????????

class Scene(BaseModel):
    index: int
    text: str
    image_prompt: str
    video_prompt: Optional[str] = None
    image_path: Optional[str] = None
    video_clip_path: Optional[str] = None
    duration_seconds: float = 0.0


class StoryResult(BaseModel):
    title: str
    full_text: str
    scenes: list[Scene]
    language: str
    word_count: int
    character_descriptions: str = ""


class PipelineContext(BaseModel):
    job_id: str
    configuration: ConfigurationCreate
    story: Optional[StoryResult] = None
    narration_path: Optional[str] = None
    subtitle_path: Optional[str] = None
    video_path: Optional[str] = None
    work_dir: str = ""
    total_cost: float = 0.0
