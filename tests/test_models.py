"""Tests for Pydantic data models."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    AppType, ConnectedAccountProvider, VerificationMethod,
    Bundle, Release, ContentRating, Urls, Icon, ScreenshotSize, Screenshot,
    Provides, Launchable, Translation, Metadata, Branding,
    DesktopAppstream, AddonAppstream, LocalizationAppstream, GenericAppstream, RuntimeAppstream,
    AppsIndex, SearchQuery, Filter,
    UserInfo, AuthInfo, Auths,
    SummaryExtension, SummaryPermissions, SummaryMetadata, SummaryExtraData, SummaryResponse,
    ListAppstreamRequest, GetAppstreamRequest, SearchAppsRequest, GetSummaryRequest,
    Platform,
)

class TestEnums:
    def test_app_type_values(self):
        assert AppType.APPS == "apps"
        assert AppType.DESKTOP == "desktop"
        assert AppType.RUNTIME == "runtime"
        assert AppType.ADDON == "addon"

    def test_connected_account_provider(self):
        assert ConnectedAccountProvider.GITHUB == "github"
        assert ConnectedAccountProvider.GITLAB == "gitlab"
        assert ConnectedAccountProvider.GNOME == "gnome"
        assert ConnectedAccountProvider.GOOGLE == "google"
        assert ConnectedAccountProvider.KDE == "kde"

    def test_verification_method(self):
        assert VerificationMethod.NONE == "none"
        assert VerificationMethod.MANUAL == "manual"
        assert VerificationMethod.WEBSITE == "website"
        assert VerificationMethod.LOGIN_PROVIDER == "login_provider"

class TestBundle:
    def test_create_bundle(self):
        b = Bundle(value="org.example.App", type="flatpak")
        assert b.value == "org.example.App"
        assert b.type == "flatpak"
        assert b.runtime is None

    def test_bundle_with_runtime(self):
        b = Bundle(value="org.example.App", type="flatpak", runtime="org.freedesktop.Platform/x86_64/23.08", sdk="org.freedesktop.Sdk/x86_64/23.08")
        assert b.runtime == "org.freedesktop.Platform/x86_64/23.08"
        assert b.sdk == "org.freedesktop.Sdk/x86_64/23.08"

class TestRelease:
    def test_create_release(self):
        r = Release(version="1.0.0")
        assert r.version == "1.0.0"
        assert r.timestamp is None

    def test_release_with_all_fields(self):
        r = Release(version="1.0.0", type="stable", urgency="medium", description="Initial release")
        assert r.type == "stable"
        assert r.urgency == "medium"
        assert r.description == "Initial release"

class TestContentRating:
    def test_empty_content_rating(self):
        cr = ContentRating()
        assert cr.type is None
        assert cr.violence_cartoon is None

    def test_content_rating_with_values(self):
        cr = ContentRating(type="oars-1.1", violence_cartoon="mild", social_chat="intense")
        assert cr.type == "oars-1.1"
        assert cr.violence_cartoon == "mild"
        assert cr.social_chat == "intense"

class TestUrls:
    def test_empty_urls(self):
        u = Urls()
        assert u.homepage is None

    def test_urls_with_values(self):
        u = Urls(homepage="https://example.com", bugtracker="https://github.com/example/issues")
        assert u.homepage == "https://example.com"

class TestIcon:
    def test_create_icon(self):
        i = Icon(url="https://example.com/icon.png", width=64, height=64)
        assert i.url == "https://example.com/icon.png"
        assert i.width == 64

class TestScreenshot:
    def test_create_screenshot(self):
        size = ScreenshotSize(width="1920", height="1080", scale="1x", src="https://example.com/ss.png")
        ss = Screenshot(sizes=[size], caption="Main window")
        assert len(ss.sizes) == 1
        assert ss.caption == "Main window"

class TestDesktopAppstream:
    def test_create_desktop_appstream(self):
        app = DesktopAppstream(
            type="desktop-application",
            id="org.example.App",
            name="Example App",
            summary="An example",
            description="Full description",
            releases=[],
            bundle=Bundle(value="org.example.App", type="flatpak"),
            is_free_license=True,
        )
        assert app.id == "org.example.App"
        assert app.is_free_license is True

class TestAddonAppstream:
    def test_create_addon(self):
        app = AddonAppstream(
            id="org.example.App.Addon",
            name="Addon",
            summary="An addon",
            extends="org.example.App",
            bundle=Bundle(value="org.example.App.Addon", type="flatpak"),
            is_free_license=True,
        )
        assert app.extends == "org.example.App"

class TestLocalizationAppstream:
    def test_create_localization(self):
        app = LocalizationAppstream(
            id="org.example.App.Locale",
            name="Locale",
            summary="Localization",
            urls=Urls(),
            bundle=Bundle(value="org.example.App.Locale", type="flatpak"),
            is_free_license=True,
        )
        assert app.type == "localization"

class TestGenericAppstream:
    def test_create_generic(self):
        app = GenericAppstream(
            id="org.example.Generic",
            name="Generic",
            summary="A generic component",
            urls=Urls(),
            bundle=Bundle(value="org.example.Generic", type="flatpak"),
            is_free_license=True,
        )
        assert app.type == "generic"

class TestRuntimeAppstream:
    def test_create_runtime(self):
        app = RuntimeAppstream(
            id="org.freedesktop.Platform",
            name="Freedesktop Platform",
            summary="Runtime",
            urls=Urls(),
            bundle=Bundle(value="org.freedesktop.Platform", type="flatpak"),
            is_free_license=True,
        )
        assert app.type == "runtime"

class TestAppsIndex:
    def test_create_apps_index(self):
        idx = AppsIndex(
            name="Test App",
            summary="A test",
            description="Description",
            id="org.example.App",
            type="desktop-application",
            project_license="MIT",
            is_free_license=True,
            app_id="org.example.App",
            main_categories=["Utility"],
            verification_verified=False,
            verification_method=VerificationMethod.NONE,
            updated_at=1700000000,
            is_mobile_friendly=False,
        )
        assert idx.app_id == "org.example.App"

class TestSearchQuery:
    def test_create_search_query(self):
        q = SearchQuery(query="test")
        assert q.query == "test"
        assert q.page == 1
        assert q.hits_per_page == 21

    def test_search_query_with_filters(self):
        f = Filter(filter_type="category", value="Game")
        q = SearchQuery(query="game", filters=[f], page=2, hits_per_page=10)
        assert len(q.filters) == 1
        assert q.page == 2

class TestUserInfo:
    def test_create_user_info(self):
        ui = UserInfo(
            displayname="Test",
            invite_code="abc",
            default_account=AuthInfo(login="test"),
            auths=Auths(),
        )
        assert ui.displayname == "Test"

class TestAuths:
    def test_empty_auths(self):
        a = Auths()
        assert a.github is None

    def test_auths_with_providers(self):
        a = Auths(github=AuthInfo(login="user", avatar="https://avatar.com"))
        assert a.github.login == "user"

class TestSummaryModels:
    def test_summary_response(self):
        sr = SummaryResponse(arches=["x86_64"], timestamp=1700000000, download_size=1000, installed_size=5000)
        assert sr.arches == ["x86_64"]

    def test_summary_metadata(self):
        sm = SummaryMetadata(name="App", runtime="org.freedesktop.Platform/x86_64/23.08")
        assert sm.name == "App"

class TestPlatform:
    def test_create_platform(self):
        p = Platform(aliases=["flathub"], keep=0)
        assert p.depends is None
        assert p.aliases == ["flathub"]

class TestRequestModels:
    def test_list_appstream_request(self):
        r = ListAppstreamRequest()
        assert r.filter == AppType.APPS
        assert r.sort == "alphabetical"

    def test_get_appstream_request(self):
        r = GetAppstreamRequest(app_id="org.example.App")
        assert r.locale == "en"

    def test_get_appstream_request_validation(self):
        with pytest.raises(Exception):
            GetAppstreamRequest(app_id="ab")  # too short

    def test_search_apps_request(self):
        r = SearchAppsRequest(query=SearchQuery(query="test"))
        assert r.locale == "en"

    def test_get_summary_request(self):
        r = GetSummaryRequest(app_id="org.example.App")
        assert r.branch is None
