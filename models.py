from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from enum import Enum

class AppType(str, Enum):
    APPS = "apps"
    DESKTOP = "desktop"
    DESKTOP_APPLICATION = "desktop-application"
    CONSOLE_APPLICATION = "console-application"
    LOCALIZATION = "localization"
    GENERIC = "generic"
    EXTENSION = "extension"
    ADDON = "addon"
    RUNTIME = "runtime"

class ConnectedAccountProvider(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    GNOME = "gnome"
    GOOGLE = "google"
    KDE = "kde"

class VerificationMethod(str, Enum):
    NONE = "none"
    MANUAL = "manual"
    WEBSITE = "website"
    LOGIN_PROVIDER = "login_provider"

# Base models for AppStream data
class Bundle(BaseModel):
    value: str
    type: str
    runtime: Optional[str] = None
    sdk: Optional[str] = None

class Release(BaseModel):
    timestamp: Optional[str] = None
    version: Optional[str] = None
    date: Optional[date] = None
    type: Optional[str] = None
    urgency: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    date_eol: Optional[date] = None

class ContentRating(BaseModel):
    type: Optional[str] = None
    violence_cartoon: Optional[str] = None
    violence_fantasy: Optional[str] = None
    violence_realistic: Optional[str] = None
    violence_bloodshed: Optional[str] = None
    violence_sexual: Optional[str] = None
    violence_desecration: Optional[str] = None
    violence_slavery: Optional[str] = None
    violence_worship: Optional[str] = None
    drugs_alcohol: Optional[str] = None
    drugs_narcotics: Optional[str] = None
    drugs_tobacco: Optional[str] = None
    sex_nudity: Optional[str] = None
    sex_themes: Optional[str] = None
    sex_homosexuality: Optional[str] = None
    sex_prostitution: Optional[str] = None
    sex_adultery: Optional[str] = None
    sex_appearance: Optional[str] = None
    language_profanity: Optional[str] = None
    language_humor: Optional[str] = None
    language_discrimination: Optional[str] = None
    social_chat: Optional[str] = None
    social_info: Optional[str] = None
    social_audio: Optional[str] = None
    social_location: Optional[str] = None
    social_contacts: Optional[str] = None
    money_purchasing: Optional[str] = None
    money_gambling: Optional[str] = None

class Urls(BaseModel):
    bugtracker: Optional[str] = None
    homepage: Optional[str] = None
    help: Optional[str] = None
    donation: Optional[str] = None
    translate: Optional[str] = None
    faq: Optional[str] = None
    contact: Optional[str] = None
    vcs_browser: Optional[str] = None
    contribute: Optional[str] = None

class Icon(BaseModel):
    url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    scale: Optional[int] = None
    type: Optional[str] = None

class ScreenshotSize(BaseModel):
    width: str
    height: str
    scale: str = "1x"
    src: str

class Screenshot(BaseModel):
    sizes: List[ScreenshotSize]
    caption: Optional[str] = None
    default: Optional[bool] = None

class Provides(BaseModel):
    value: str
    type: str

class Launchable(BaseModel):
    value: str
    type: str

class Translation(BaseModel):
    value: Optional[str] = None
    type: Optional[str] = None

class Metadata(BaseModel):
    flathub_manifest: Optional[str] = Field(None, alias="flathub::manifest")
    flathub_verification_verified: Optional[bool] = Field(None, alias="flathub::verification::verified")
    flathub_verification_method: Optional[str] = Field(None, alias="flathub::verification::method")
    flathub_verification_login_name: Optional[str] = Field(None, alias="flathub::verification::login_name")
    flathub_verification_login_provider: Optional[ConnectedAccountProvider] = Field(None, alias="flathub::verification::login_provider")
    flathub_verification_website: Optional[str] = Field(None, alias="flathub::verification::website")
    flathub_verification_timestamp: Optional[str] = Field(None, alias="flathub::verification::timestamp")
    flathub_verification_login_is_organization: Optional[bool] = Field(None, alias="flathub::verification::login_is_organization")

class Branding(BaseModel):
    value: str
    scheme_preference: Optional[str] = None
    type: str = "primary"

# Main AppStream models
class DesktopAppstream(BaseModel):
    type: str
    id: str
    name: str
    summary: str
    description: str
    developer_name: Optional[str] = None
    icon: Optional[str] = None
    icons: Optional[List[Icon]] = None
    screenshots: Optional[List[Screenshot]] = None
    releases: List[Release]
    content_rating: Optional[ContentRating] = None
    urls: Optional[Urls] = None
    categories: Optional[List[str]] = None
    kudos: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    mimetypes: Optional[List[str]] = None
    project_license: Optional[str] = None
    provides: Optional[List[Union[Provides, str]]] = None
    launchable: Optional[Launchable] = None
    bundle: Bundle
    translation: Optional[Translation] = None
    metadata: Optional[Metadata] = None
    is_free_license: bool
    is_mobile_friendly: Optional[bool] = None
    branding: Optional[List[Branding]] = None

class AddonAppstream(BaseModel):
    type: str = "addon"
    id: str
    name: str
    summary: str
    releases: Optional[List[Release]] = None
    content_rating: Optional[ContentRating] = None
    urls: Optional[Urls] = None
    categories: Optional[List[str]] = None
    icon: Optional[str] = None
    icons: Optional[List[Icon]] = None
    developer_name: Optional[str] = None
    project_license: Optional[str] = None
    extends: str
    bundle: Bundle
    metadata: Optional[Metadata] = None
    is_mobile_friendly: Optional[bool] = None
    is_free_license: bool

class LocalizationAppstream(BaseModel):
    type: str = "localization"
    id: str
    name: str
    summary: str
    releases: Optional[List[Release]] = None
    urls: Urls
    categories: Optional[List[str]] = None
    icon: Optional[str] = None
    icons: Optional[List[Icon]] = None
    developer_name: Optional[str] = None
    project_license: Optional[str] = None
    bundle: Bundle
    metadata: Optional[Metadata] = None
    is_mobile_friendly: Optional[bool] = None
    is_free_license: bool

class GenericAppstream(BaseModel):
    type: str = "generic"
    id: str
    name: str
    summary: str
    releases: Optional[List[Release]] = None
    urls: Urls
    categories: Optional[List[str]] = None
    icon: Optional[str] = None
    icons: Optional[List[Icon]] = None
    developer_name: Optional[str] = None
    project_license: Optional[str] = None
    bundle: Bundle
    metadata: Optional[Metadata] = None
    is_mobile_friendly: Optional[bool] = None
    is_free_license: bool

class RuntimeAppstream(BaseModel):
    type: str = "runtime"
    id: str
    name: str
    summary: str
    description: Optional[str] = None
    releases: Optional[List[Release]] = None
    urls: Urls
    categories: Optional[List[str]] = None
    icon: Optional[str] = None
    icons: Optional[List[Icon]] = None
    developer_name: Optional[str] = None
    project_license: Optional[str] = None
    bundle: Bundle
    metadata: Optional[Metadata] = None
    is_mobile_friendly: Optional[bool] = None
    is_free_license: bool

# Search and indexing models
class AppsIndex(BaseModel):
    name: str
    keywords: Optional[List[str]] = None
    summary: str
    description: str
    id: str
    type: str
    translations: Optional[Dict[str, Dict[str, Union[str, List[str]]]]] = None
    project_license: str
    is_free_license: bool
    app_id: str
    icon: Optional[str] = None
    main_categories: Union[str, List[str]]
    sub_categories: Optional[List[str]] = None
    developer_name: Optional[str] = None
    verification_verified: bool
    verification_method: VerificationMethod
    verification_login_name: Optional[str] = None
    verification_login_provider: Optional[ConnectedAccountProvider] = None
    verification_login_is_organization: Optional[bool] = None
    verification_website: Optional[str] = None
    verification_timestamp: Optional[str] = None
    runtime: Optional[str] = None
    updated_at: int
    arches: Optional[List[str]] = None
    added_at: Optional[int] = None
    trending: Optional[float] = None
    installs_last_month: Optional[int] = None
    favorites_count: Optional[int] = None
    is_mobile_friendly: bool

class SearchQuery(BaseModel):
    query: str
    filters: Optional[List['Filter']] = None
    hits_per_page: int = 21
    page: int = 1

class Filter(BaseModel):
    filter_type: str
    value: str

# Auth models
class UserInfo(BaseModel):
    displayname: Optional[str] = None
    dev_flatpaks: List[str] = []
    permissions: List[str] = []
    owned_flatpaks: List[str] = []
    invited_flatpaks: List[str] = []
    invite_code: str
    accepted_publisher_agreement_at: Optional[datetime] = None
    default_account: 'AuthInfo'
    auths: 'Auths'

class AuthInfo(BaseModel):
    login: str
    avatar: Optional[str] = None

class Auths(BaseModel):
    github: Optional[AuthInfo] = None
    gitlab: Optional[AuthInfo] = None
    gnome: Optional[AuthInfo] = None
    kde: Optional[AuthInfo] = None

# Summary models
class SummaryExtension(BaseModel):
    directory: Optional[str] = None
    autodelete: Optional[str] = None
    no_autodownload: Optional[str] = Field(None, alias="noAutodownload")
    version: Optional[str] = None
    versions: Optional[str] = None

class SummaryPermissions(BaseModel):
    shared: Optional[List[str]] = None
    sockets: Optional[List[str]] = None
    devices: Optional[List[str]] = None
    filesystems: Optional[List[str]] = None
    session_bus: Optional[Dict[str, List[str]]] = Field(None, alias="session-bus")

class SummaryMetadata(BaseModel):
    name: str
    runtime: str
    sdk: Optional[str] = None
    tags: Optional[List[str]] = None
    command: Optional[str] = None
    permissions: Optional[SummaryPermissions] = None
    extensions: Optional[Dict[str, SummaryExtension]] = None
    built_extensions: Optional[List[str]] = Field(None, alias="builtExtensions")
    extra_data: Optional['SummaryExtraData'] = Field(None, alias="extraData")
    runtime_is_eol: bool = Field(False, alias="runtimeIsEol")

class SummaryExtraData(BaseModel):
    name: str
    checksum: str
    size: str
    uri: str

class SummaryResponse(BaseModel):
    arches: List[str]
    branch: Optional[str] = None
    timestamp: int
    download_size: int
    installed_size: int
    metadata: Optional[SummaryMetadata] = None

# Request/Response models for API endpoints
class ListAppstreamRequest(BaseModel):
    filter: AppType = AppType.APPS
    sort: str = "alphabetical"

class GetAppstreamRequest(BaseModel):
    app_id: str = Field(..., min_length=6, max_length=255, pattern=r"^[A-Za-z_][\w\-\.]+$")
    locale: str = "en"

class SearchAppsRequest(BaseModel):
    locale: str = "en"
    query: SearchQuery

class GetSummaryRequest(BaseModel):
    app_id: str = Field(..., min_length=6, max_length=255, pattern=r"^[A-Za-z_][\w\-\.]+$")
    branch: Optional[str] = None

# Platform models
class Platform(BaseModel):
    depends: Optional[str] = None
    aliases: List[str]
    keep: int
    stripe_account: Optional[str] = None

# Update forward references (Pydantic v2)
UserInfo.model_rebuild()
Auths.model_rebuild()
SearchQuery.model_rebuild()
Filter.model_rebuild()
SummaryMetadata.model_rebuild()