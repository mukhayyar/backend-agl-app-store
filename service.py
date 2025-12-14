import grpc
from concurrent import futures
import logging
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func

from google.protobuf.empty_pb2 import Empty as ProtoEmpty
from generated import pens_agl_store_pb2, pens_agl_store_pb2_grpc
from models import *
from database import SessionLocal, App, User, Category, Release, Favorite, AppStats, Transaction, TransactionDetail

logger = logging.getLogger(__name__)

class PENSAGLStoreService(pens_agl_store_pb2_grpc.FlathubServiceServicer):

    def _get_db(self):
        """Create a new database session for each request."""
        return SessionLocal()

    def GetEolRebase(self, request, context):
        db = self._get_db()
        try:
            # Implementation for getting EOL rebase information
            eol_data = {}
            # Query database for EOL rebase info
            apps = db.query(App).all()
            for app in apps:
                # This would come from a dedicated EOL table in real implementation
                eol_data[app.id] = []
            
            return pens_agl_store_pb2.EolRebaseResponse(rebase_info=eol_data)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting EOL rebase: {str(e)}")
            return pens_agl_store_pb2.EolRebaseResponse()
        finally:
            db.close()

    def GetEolRebaseAppId(self, request, context):
        db = self._get_db()
        try:
            app = db.query(App).filter(App.id == request.app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.EolRebaseAppIdResponse()
            
            # In real implementation, this would query EOL specific data
            rebase_info = ""  # This would come from EOL table
            
            return pens_agl_store_pb2.EolRebaseAppIdResponse(rebase_info=rebase_info)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting EOL rebase for app: {str(e)}")
            return pens_agl_store_pb2.EolRebaseAppIdResponse()
        finally:
            db.close()

    def GetEolMessage(self, request, context):
        try:
            eol_messages = {}
            # Query EOL messages from database
            return pens_agl_store_pb2.EolMessageResponse(messages=eol_messages)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting EOL messages: {str(e)}")
            return pens_agl_store_pb2.EolMessageResponse()
    
    def GetEolMessageAppId(self, request, context):
        db = self._get_db()
        try:
            app = db.query(App).filter(App.id == request.app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.EolMessageAppIdResponse()
            
            # Get EOL message for specific app
            message = ""  # From EOL table
            
            return pens_agl_store_pb2.EolMessageAppIdResponse(message=message)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting EOL message for app: {str(e)}")
            return pens_agl_store_pb2.EolMessageAppIdResponse()
        finally:
            db.close()

    def ListAppstream(self, request, context):
        db = self._get_db()
        try:
            # Build query based on filter and sort
            query = db.query(App.id)
            
            # Apply filter
            if request.filter:
                query = query.filter(App.type == request.filter)
            
            # Apply sort
            if request.sort == "alphabetical":
                query = query.order_by(App.id)
            elif request.sort == "created-at":
                query = query.order_by(desc(App.added_at))
            elif request.sort == "last-updated-at":
                query = query.order_by(desc(App.updated_at))
            
            app_ids = [app.id for app in query.all()]
            
            return pens_agl_store_pb2.ListAppstreamResponse(app_ids=app_ids)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error listing appstream: {str(e)}")
            return pens_agl_store_pb2.ListAppstreamResponse()
        finally:
            db.close()

    def GetAppstream(self, request, context):
        db = self._get_db()
        try:
            app = db.query(App).filter(App.id == request.app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.GetAppstreamResponse()
            
            # Convert database app to appropriate AppStream type
            if app.type in ["desktop-application", "console-application", "desktop"]:
                desktop_app = self._convert_to_desktop_appstream(app)
                return pens_agl_store_pb2.GetAppstreamResponse(desktop=desktop_app)
            elif app.type == "addon":
                addon_app = self._convert_to_addon_appstream(app)
                return pens_agl_store_pb2.GetAppstreamResponse(addon=addon_app)
            elif app.type == "localization":
                localization_app = self._convert_to_localization_appstream(app)
                return pens_agl_store_pb2.GetAppstreamResponse(localization=localization_app)
            elif app.type == "generic":
                generic_app = self._convert_to_generic_appstream(app)
                return pens_agl_store_pb2.GetAppstreamResponse(generic=generic_app)
            elif app.type == "runtime":
                runtime_app = self._convert_to_runtime_appstream(app)
                return pens_agl_store_pb2.GetAppstreamResponse(runtime=runtime_app)
            else:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(f"Unknown app type: {app.type}")
                return pens_agl_store_pb2.GetAppstreamResponse()
                
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting appstream: {str(e)}")
            return pens_agl_store_pb2.GetAppstreamResponse()
        finally:
            db.close()

    def GetIsFullscreenApp(self, request, context):
        try:
            # In real implementation, this would check app metadata for fullscreen configuration
            # For now, return False for all apps
            return pens_agl_store_pb2.GetIsFullscreenAppResponse(is_fullscreen=False)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error checking fullscreen app: {str(e)}")
            return pens_agl_store_pb2.GetIsFullscreenAppResponse(is_fullscreen=False)
    
    def SearchApps(self, request, context):
        db = self._get_db()
        try:
            search_query = request.query.query.lower() if request.query.query else ""

            # Build search query
            query = db.query(App)
            
            if search_query:
                query = query.filter(
                    or_(
                        App.name.ilike(f"%{search_query}%"),
                        App.summary.ilike(f"%{search_query}%"),
                        App.description.ilike(f"%{search_query}%"),
                        App.id.ilike(f"%{search_query}%")
                    )
                )
            
            # Apply filters
            if request.query.filters:
                for filter_obj in request.query.filters:
                    if filter_obj.filter_type == "category":
                        query = query.join(App.categories).filter(Category.name == filter_obj.value)
                    elif filter_obj.filter_type == "runtime":
                        query = query.filter(App.runtime == filter_obj.value)
            
            # Pagination
            page = request.query.page or 1
            hits_per_page = request.query.hits_per_page or 21
            offset = (page - 1) * hits_per_page
            
            total_hits = query.count()
            total_pages = (total_hits + hits_per_page - 1) // hits_per_page
            
            apps = query.offset(offset).limit(hits_per_page).all()
            
            # Convert to AppsIndex format
            hits = [self._convert_to_apps_index(app) for app in apps]
            
            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query=search_query,
                processing_time_ms=0,  # Would calculate in real implementation
                hits_per_page=hits_per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error searching apps: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    def GetRuntimeList(self, request, context):
        db = self._get_db()
        try:
            # Count apps per runtime
            runtime_counts = (
                db.query(App.runtime, func.count(App.id))
                .filter(App.runtime.isnot(None))
                .group_by(App.runtime)
                .all()
            )
            
            runtimes = {runtime: count for runtime, count in runtime_counts if runtime}
            
            return pens_agl_store_pb2.RuntimeListResponse(runtimes=runtimes)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting runtime list: {str(e)}")
            return pens_agl_store_pb2.RuntimeListResponse()
        finally:
            db.close()

    def GetSummary(self, request, context):
        db = self._get_db()
        try:
            app = db.query(App).filter(App.id == request.app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.SummaryResponse()
            
            # Convert to summary response
            summary = pens_agl_store_pb2.SummaryResponse(
                arches=["x86_64"],  # Would get from app metadata
                branch=request.branch or "stable",
                timestamp=int(app.updated_at.timestamp()) if app.updated_at else 0,
                download_size=0,  # Would calculate from actual package size
                installed_size=0,  # Would calculate from actual package size
                metadata=pens_agl_store_pb2.SummaryMetadata(
                    name=app.name,
                    runtime=app.runtime or "",
                    sdk=app.runtime  # Assuming SDK same as runtime for simplicity
                )
            )
            
            return summary
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting summary: {str(e)}")
            return pens_agl_store_pb2.SummaryResponse()
        finally:
            db.close()

    def GetPlatforms(self, request, context):
        try:
            # Define available platforms
            platforms = {
                "org.flathub.Flathub": pens_agl_store_pb2.Platform(
                    depends=None,
                    aliases=["flathub"],
                    keep=0,
                    stripe_account=None
                )
            }
            
            return pens_agl_store_pb2.PlatformsResponse(platforms=platforms)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting platforms: {str(e)}")
            return pens_agl_store_pb2.PlatformsResponse()
    
    def GetAddons(self, request, context):
        db = self._get_db()
        try:
            # Find addons that extend this app
            addons = (
                db.query(App.id)
                .filter(App.type == "addon")
                .filter(App.extends == request.app_id)  # Assuming extends field exists
                .all()
            )
            
            addon_ids = [addon.id for addon in addons]
            
            return pens_agl_store_pb2.GetAddonsResponse(addons=addon_ids)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting addons: {str(e)}")
            return pens_agl_store_pb2.GetAddonsResponse()
        finally:
            db.close()

    # Auth methods
    def GetLoginMethods(self, request, context):
        try:
            methods = [
                pens_agl_store_pb2.LoginMethod(method="github", name="GitHub"),
                pens_agl_store_pb2.LoginMethod(method="gitlab", name="GitLab"),
                pens_agl_store_pb2.LoginMethod(method="gnome", name="GNOME"),
                pens_agl_store_pb2.LoginMethod(method="kde", name="KDE"),
                pens_agl_store_pb2.LoginMethod(method="google", name="Google")
            ]
            return pens_agl_store_pb2.LoginMethodsResponse(methods=methods)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting login methods: {str(e)}")
            return pens_agl_store_pb2.LoginMethodsResponse()
    
    def GetUserInfo(self, request, context):
        db = self._get_db()
        try:
            # Extract user from context (would be set by auth middleware)
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                return pens_agl_store_pb2.UserInfoResponse(not_logged_in=ProtoEmpty())
            
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return pens_agl_store_pb2.UserInfoResponse(not_logged_in=ProtoEmpty())
            
            # Get user's developed apps
            dev_flatpaks = [app.id for app in user.developed_apps]
            
            user_info = pens_agl_store_pb2.UserInfo(
                displayname=user.display_name,
                dev_flatpaks=dev_flatpaks,
                permissions=[],  # Would get from user roles
                owned_flatpaks=[],  # Would get from purchase records
                invited_flatpaks=[],  # Would get from invites
                invite_code=user.invite_code,
                accepted_publisher_agreement_at=user.accepted_publisher_agreement_at.isoformat() if user.accepted_publisher_agreement_at else "",
                default_account=pens_agl_store_pb2.AuthInfo(
                    login=user.default_account_login or "",
                    avatar=""
                ),
                auths=pens_agl_store_pb2.Auths()
            )
            
            return pens_agl_store_pb2.UserInfoResponse(user_info=user_info)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting user info: {str(e)}")
            return pens_agl_store_pb2.UserInfoResponse()
        finally:
            db.close()

    def RefreshDevFlatpaks(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.RefreshDevFlatpaksResponse()

            # In real implementation, this would refresh from connected GitHub account
            # For now, return current dev flatpaks
            user = db.query(User).filter(User.id == user_id).first()
            dev_flatpaks = [app.id for app in user.developed_apps] if user else []
            
            return pens_agl_store_pb2.RefreshDevFlatpaksResponse(dev_flatpaks=dev_flatpaks)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error refreshing dev flatpaks: {str(e)}")
            return pens_agl_store_pb2.RefreshDevFlatpaksResponse()
        finally:
            db.close()

    # Collection methods
    def GetCategories(self, request, context):
        db = self._get_db()
        try:
            categories = db.query(Category.name).all()
            category_names = [cat.name for cat in categories]
            
            return pens_agl_store_pb2.CategoriesResponse(categories=category_names)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting categories: {str(e)}")
            return pens_agl_store_pb2.CategoriesResponse()
        finally:
            db.close()

    def GetCategory(self, request, context):
        try:
            # Build search request for this category
            search_query = pens_agl_store_pb2.SearchQuery(
                query="",
                filters=[pens_agl_store_pb2.Filter(filter_type="category", value=request.category)],
                page=request.page or 1,
                hits_per_page=request.per_page or 21
            )
            
            search_request = pens_agl_store_pb2.SearchAppsRequest(
                locale=request.locale or "en",
                query=search_query
            )
            
            return self.SearchApps(search_request, context)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting category: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
    
    def GetRecentlyUpdated(self, request, context):
        db = self._get_db()
        try:
            # Query recently updated apps
            apps = (
                db.query(App)
                .order_by(desc(App.updated_at))
                .offset((request.page - 1) * request.per_page if request.page else 0)
                .limit(request.per_page or 21)
                .all()
            )
            
            hits = [self._convert_to_apps_index(app) for app in apps]
            
            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query="",
                hits_per_page=request.per_page or 21,
                page=request.page or 1,
                total_pages=1,  # Would calculate properly
                total_hits=len(apps)
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting recently updated: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    # Favorites methods
    def AddToFavorites(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return ProtoEmpty()

            app = db.query(App).filter(App.id == request.app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return ProtoEmpty()
            
            # Check if already favorited
            existing_favorite = (
                db.query(Favorite)
                .filter(Favorite.user_id == user_id, Favorite.app_id == request.app_id)
                .first()
            )
            
            if not existing_favorite:
                favorite = Favorite(user_id=user_id, app_id=request.app_id)
                db.add(favorite)
                db.commit()
            
            return ProtoEmpty()
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error adding to favorites: {str(e)}")
            return ProtoEmpty()
        finally:
            db.close()

    def RemoveFromFavorites(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return ProtoEmpty()

            favorite = (
                db.query(Favorite)
                .filter(Favorite.user_id == user_id, Favorite.app_id == request.app_id)
                .first()
            )
            
            if favorite:
                db.delete(favorite)
                db.commit()
            
            return ProtoEmpty()
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error removing from favorites: {str(e)}")
            return ProtoEmpty()
        finally:
            db.close()

    def GetFavorites(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                return pens_agl_store_pb2.GetFavoritesResponse(favorites=[])

            favorites = (
                db.query(Favorite)
                .filter(Favorite.user_id == user_id)
                .order_by(desc(Favorite.created_at))
                .all()
            )
            
            favorite_apps = [
                pens_agl_store_pb2.FavoriteApp(
                    app_id=fav.app_id,
                    created_at=fav.created_at.isoformat()
                )
                for fav in favorites
            ]
            
            return pens_agl_store_pb2.GetFavoritesResponse(favorites=favorite_apps)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting favorites: {str(e)}")
            return pens_agl_store_pb2.GetFavoritesResponse()
        finally:
            db.close()

    def IsFavorited(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                return pens_agl_store_pb2.IsFavoritedResponse(is_favorited=False)

            favorite = (
                db.query(Favorite)
                .filter(Favorite.user_id == user_id, Favorite.app_id == request.app_id)
                .first()
            )
            
            return pens_agl_store_pb2.IsFavoritedResponse(is_favorited=bool(favorite))
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error checking favorite: {str(e)}")
            return pens_agl_store_pb2.IsFavoritedResponse(is_favorited=False)
        finally:
            db.close()

    # Stats methods
    def GetStats(self, request, context):
        db = self._get_db()
        try:
            # Calculate overall stats
            total_apps = db.query(App).count()
            total_downloads = db.query(func.sum(AppStats.installs)).scalar() or 0
            
            stats = pens_agl_store_pb2.StatsResult(
                totals={
                    "apps": total_apps,
                    "downloads": total_downloads
                },
                countries={},
                downloads_per_day={},
                updates_per_day={},
                delta_downloads_per_day={},
                category_totals=[]
            )
            
            return pens_agl_store_pb2.StatsResultResponse(stats=stats)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting stats: {str(e)}")
            return pens_agl_store_pb2.StatsResultResponse()
        finally:
            db.close()

    def GetStatsForApp(self, request, context):
        db = self._get_db()
        try:
            app = db.query(App).filter(App.id == request.app_id).first()
            if not app:
                return pens_agl_store_pb2.StatsResultAppResponse(not_found=ProtoEmpty())
            
            # Calculate app stats
            total_installs = (
                db.query(func.sum(AppStats.installs))
                .filter(AppStats.app_id == request.app_id)
                .scalar() or 0
            )
            
            stats = pens_agl_store_pb2.StatsResultApp(
                installs_total=total_installs,
                installs_per_day={},
                installs_per_country={},
                installs_last_month=0,  # Would calculate properly
                installs_last_7_days=0,  # Would calculate properly
                id=request.app_id
            )
            
            return pens_agl_store_pb2.StatsResultAppResponse(stats=stats)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting app stats: {str(e)}")
            return pens_agl_store_pb2.StatsResultAppResponse()
        finally:
            db.close()

    def Healthcheck(self, request, context):
        db = self._get_db()
        try:
            # Simple health check - verify database connection
            db.query(App).limit(1).first()
            return ProtoEmpty()
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Health check failed: {str(e)}")
            return ProtoEmpty()
        finally:
            db.close()

    # Helper methods
    def _get_user_id_from_context(self, context):
        """Extract user ID from gRPC context metadata"""
        # In real implementation, this would extract from JWT or session
        # For now, return a dummy user ID
        return 1
    
    def _convert_to_apps_index(self, app):
        """Convert database App to AppsIndex proto message"""
        return pens_agl_store_pb2.AppsIndex(
            name=app.name,
            summary=app.summary or "",
            description=app.description or "",
            id=app.id,
            type=app.type,
            project_license=app.project_license or "",
            is_free_license=app.is_free_license,
            app_id=app.id,
            icon=app.icon or "",
            main_categories=[cat.name for cat in app.categories],
            developer_name=app.developer_name or "",
            verification_verified=app.verification_verified,
            verification_method=app.verification_method,
            verification_login_name=app.verification_login_name or "",
            verification_login_provider=app.verification_login_provider or "",
            verification_login_is_organization=app.verification_login_is_organization,
            verification_website=app.verification_website or "",
            verification_timestamp=app.verification_timestamp.isoformat() if app.verification_timestamp else "",
            runtime=app.runtime or "",
            updated_at=int(app.updated_at.timestamp()) if app.updated_at else 0,
            added_at=int(app.added_at.timestamp()) if app.added_at else 0,
            is_mobile_friendly=app.is_mobile_friendly
        )
    
    def _convert_to_desktop_appstream(self, app):
        """Convert database App to DesktopAppstream proto message"""
        return pens_agl_store_pb2.DesktopAppstream(
            type=app.type,
            id=app.id,
            name=app.name,
            summary=app.summary or "",
            description=app.description or "",
            developer_name=app.developer_name,
            icon=app.icon,
            releases=[],  # Would populate from releases table
            bundle=pens_agl_store_pb2.Bundle(
                value=app.id,
                type="flatpak",
                runtime=app.runtime
            ),
            is_free_license=app.is_free_license,
            is_mobile_friendly=app.is_mobile_friendly
        )
    
    def _convert_to_addon_appstream(self, app):
        """Convert database App to AddonAppstream proto message"""
        return pens_agl_store_pb2.AddonAppstream(
            type=app.type,
            id=app.id,
            name=app.name,
            summary=app.summary or "",
            extends="",  # Would get from app metadata
            bundle=pens_agl_store_pb2.Bundle(
                value=app.id,
                type="flatpak",
                runtime=app.runtime
            ),
            is_free_license=app.is_free_license
        )
    
    def _convert_to_localization_appstream(self, app):
        """Convert database App to LocalizationAppstream proto message"""
        return pens_agl_store_pb2.LocalizationAppstream(
            type=app.type,
            id=app.id,
            name=app.name,
            summary=app.summary or "",
            urls=pens_agl_store_pb2.Urls(),
            bundle=pens_agl_store_pb2.Bundle(
                value=app.id,
                type="flatpak",
                runtime=app.runtime
            ),
            is_free_license=app.is_free_license
        )
    
    def _convert_to_generic_appstream(self, app):
        """Convert database App to GenericAppstream proto message"""
        return pens_agl_store_pb2.GenericAppstream(
            type=app.type,
            id=app.id,
            name=app.name,
            summary=app.summary or "",
            urls=pens_agl_store_pb2.Urls(),
            bundle=pens_agl_store_pb2.Bundle(
                value=app.id,
                type="flatpak",
                runtime=app.runtime
            ),
            is_free_license=app.is_free_license
        )
    
    def _convert_to_runtime_appstream(self, app):
        """Convert database App to RuntimeAppstream proto message"""
        return pens_agl_store_pb2.RuntimeAppstream(
            type=app.type,
            id=app.id,
            name=app.name,
            summary=app.summary or "",
            urls=pens_agl_store_pb2.Urls(),
            bundle=pens_agl_store_pb2.Bundle(
                value=app.id,
                type="flatpak",
                runtime=app.runtime
            ),
            is_free_license=app.is_free_license
        )

    # =====================================================================
    # OAuth Flow Methods
    # =====================================================================

    def StartGithubFlow(self, request, context):
        try:
            import uuid
            state = str(uuid.uuid4())
            redirect_url = (
                f"https://github.com/login/oauth/authorize"
                f"?client_id=GITHUB_CLIENT_ID&state={state}"
                f"&scope=read:user,user:email"
            )
            return pens_agl_store_pb2.StartOAuthFlowResponse(redirect_url=redirect_url)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error starting GitHub flow: {str(e)}")
            return pens_agl_store_pb2.StartOAuthFlowResponse()

    def ContinueGithubFlow(self, request, context):
        try:
            # In real implementation, exchange code for token and create/login user
            code = request.code if hasattr(request, 'code') else ""
            state = request.state if hasattr(request, 'state') else ""
            logger.info(f"Continuing GitHub OAuth flow with code={code}, state={state}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse(
                login_token="github_token_placeholder",
                is_new_user=False
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error continuing GitHub flow: {str(e)}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse()

    def StartGitlabFlow(self, request, context):
        try:
            import uuid
            state = str(uuid.uuid4())
            redirect_url = (
                f"https://gitlab.com/oauth/authorize"
                f"?client_id=GITLAB_CLIENT_ID&state={state}"
                f"&response_type=code&scope=read_user"
            )
            return pens_agl_store_pb2.StartOAuthFlowResponse(redirect_url=redirect_url)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error starting GitLab flow: {str(e)}")
            return pens_agl_store_pb2.StartOAuthFlowResponse()

    def ContinueGitlabFlow(self, request, context):
        try:
            code = request.code if hasattr(request, 'code') else ""
            state = request.state if hasattr(request, 'state') else ""
            logger.info(f"Continuing GitLab OAuth flow with code={code}, state={state}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse(
                login_token="gitlab_token_placeholder",
                is_new_user=False
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error continuing GitLab flow: {str(e)}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse()

    def StartGnomeFlow(self, request, context):
        try:
            import uuid
            state = str(uuid.uuid4())
            redirect_url = (
                f"https://gitlab.gnome.org/oauth/authorize"
                f"?client_id=GNOME_CLIENT_ID&state={state}"
                f"&response_type=code&scope=read_user"
            )
            return pens_agl_store_pb2.StartOAuthFlowResponse(redirect_url=redirect_url)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error starting GNOME flow: {str(e)}")
            return pens_agl_store_pb2.StartOAuthFlowResponse()

    def ContinueGnomeFlow(self, request, context):
        try:
            code = request.code if hasattr(request, 'code') else ""
            state = request.state if hasattr(request, 'state') else ""
            logger.info(f"Continuing GNOME OAuth flow with code={code}, state={state}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse(
                login_token="gnome_token_placeholder",
                is_new_user=False
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error continuing GNOME flow: {str(e)}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse()

    def StartKdeFlow(self, request, context):
        try:
            import uuid
            state = str(uuid.uuid4())
            redirect_url = (
                f"https://invent.kde.org/oauth/authorize"
                f"?client_id=KDE_CLIENT_ID&state={state}"
                f"&response_type=code&scope=read_user"
            )
            return pens_agl_store_pb2.StartOAuthFlowResponse(redirect_url=redirect_url)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error starting KDE flow: {str(e)}")
            return pens_agl_store_pb2.StartOAuthFlowResponse()

    def ContinueKdeFlow(self, request, context):
        try:
            code = request.code if hasattr(request, 'code') else ""
            state = request.state if hasattr(request, 'state') else ""
            logger.info(f"Continuing KDE OAuth flow with code={code}, state={state}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse(
                login_token="kde_token_placeholder",
                is_new_user=False
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error continuing KDE flow: {str(e)}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse()

    def ContinueGoogleFlow(self, request, context):
        try:
            code = request.code if hasattr(request, 'code') else ""
            state = request.state if hasattr(request, 'state') else ""
            logger.info(f"Continuing Google OAuth flow with code={code}, state={state}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse(
                login_token="google_token_placeholder",
                is_new_user=False
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error continuing Google flow: {str(e)}")
            return pens_agl_store_pb2.ContinueOAuthFlowResponse()

    # =====================================================================
    # Auth Methods
    # =====================================================================

    def Logout(self, request, context):
        try:
            from google.protobuf.empty_pb2 import Empty
            user_id = self._get_user_id_from_context(context)
            if user_id:
                logger.info(f"User {user_id} logged out")
            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error during logout: {str(e)}")
            return Empty()

    def GetDeleteUser(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.GetDeleteUserResponse()

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("User not found")
                return pens_agl_store_pb2.GetDeleteUserResponse()

            # Return info about what would be deleted
            return pens_agl_store_pb2.GetDeleteUserResponse(
                display_name=user.display_name or "",
                dev_flatpaks=[app.id for app in user.developed_apps] if hasattr(user, 'developed_apps') else [],
                has_active_transactions=False
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting delete user info: {str(e)}")
            return pens_agl_store_pb2.GetDeleteUserResponse()
        finally:
            db.close()

    def DeleteUser(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.DeleteUserResponse()

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("User not found")
                return pens_agl_store_pb2.DeleteUserResponse()

            # Delete user's favorites
            db.query(Favorite).filter(Favorite.user_id == user_id).delete()
            # Delete the user
            db.delete(user)
            db.commit()

            return pens_agl_store_pb2.DeleteUserResponse(deleted=True)
        except Exception as e:
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error deleting user: {str(e)}")
            return pens_agl_store_pb2.DeleteUserResponse()
        finally:
            db.close()

    def AcceptPublisherAgreement(self, request, context):
        db = self._get_db()
        try:
            from google.protobuf.empty_pb2 import Empty
            from datetime import datetime

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.accepted_publisher_agreement_at = datetime.utcnow()
                db.commit()

            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error accepting publisher agreement: {str(e)}")
            return Empty()
        finally:
            db.close()

    def ChangeDefaultAccount(self, request, context):
        db = self._get_db()
        try:
            from google.protobuf.empty_pb2 import Empty

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.default_account_login = request.login if hasattr(request, 'login') else ""
                db.commit()

            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error changing default account: {str(e)}")
            return Empty()
        finally:
            db.close()

    # =====================================================================
    # Wallet Methods
    # =====================================================================

    def GetWalletInfo(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.WalletInfoResponse()

            return pens_agl_store_pb2.WalletInfoResponse(
                status="ok",
                cards=[],
                default_card=""
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting wallet info: {str(e)}")
            return pens_agl_store_pb2.WalletInfoResponse()

    def RemoveCard(self, request, context):
        try:
            from google.protobuf.empty_pb2 import Empty

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            card_id = request.card_id if hasattr(request, 'card_id') else ""
            logger.info(f"Removing card {card_id} for user {user_id}")
            # In real implementation, would remove card from Stripe
            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error removing card: {str(e)}")
            return Empty()

    def GetTransactions(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.GetTransactionsResponse()

            transactions = (
                db.query(Transaction)
                .filter(Transaction.user_id == user_id)
                .order_by(desc(Transaction.created_at))
                .all()
            )

            transaction_list = []
            for txn in transactions:
                transaction_list.append(pens_agl_store_pb2.TransactionSummary(
                    id=str(txn.id),
                    status=txn.status or "pending",
                    amount=txn.amount or 0,
                    currency=txn.currency or "USD",
                    app_id=txn.app_id or "",
                    created_at=txn.created_at.isoformat() if txn.created_at else "",
                    updated_at=txn.updated_at.isoformat() if txn.updated_at else ""
                ))

            return pens_agl_store_pb2.GetTransactionsResponse(transactions=transaction_list)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting transactions: {str(e)}")
            return pens_agl_store_pb2.GetTransactionsResponse()
        finally:
            db.close()

    def CreateTransaction(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.CreateTransactionResponse()

            from datetime import datetime
            txn = Transaction(
                user_id=user_id,
                app_id=request.app_id if hasattr(request, 'app_id') else "",
                amount=request.amount if hasattr(request, 'amount') else 0,
                currency=request.currency if hasattr(request, 'currency') else "USD",
                status="new",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(txn)
            db.commit()
            db.refresh(txn)

            return pens_agl_store_pb2.CreateTransactionResponse(
                id=str(txn.id),
                status="new"
            )
        except Exception as e:
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error creating transaction: {str(e)}")
            return pens_agl_store_pb2.CreateTransactionResponse()
        finally:
            db.close()

    def GetTransactionById(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.TransactionResponse()

            txn = (
                db.query(Transaction)
                .filter(Transaction.id == request.transaction_id, Transaction.user_id == user_id)
                .first()
            )

            if not txn:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Transaction not found")
                return pens_agl_store_pb2.TransactionResponse()

            # Get transaction details
            details = (
                db.query(TransactionDetail)
                .filter(TransactionDetail.transaction_id == txn.id)
                .all()
            )

            detail_list = [
                pens_agl_store_pb2.TransactionDetailInfo(
                    app_id=d.app_id or "",
                    amount=d.amount or 0,
                    currency=d.currency or "USD",
                    kind=d.kind or ""
                )
                for d in details
            ]

            return pens_agl_store_pb2.TransactionResponse(
                id=str(txn.id),
                status=txn.status or "pending",
                amount=txn.amount or 0,
                currency=txn.currency or "USD",
                app_id=txn.app_id or "",
                card_id=txn.card_id or "" if hasattr(txn, 'card_id') else "",
                details=detail_list,
                created_at=txn.created_at.isoformat() if txn.created_at else "",
                updated_at=txn.updated_at.isoformat() if txn.updated_at else ""
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting transaction: {str(e)}")
            return pens_agl_store_pb2.TransactionResponse()
        finally:
            db.close()

    def SetTransactionCard(self, request, context):
        db = self._get_db()
        try:
            from google.protobuf.empty_pb2 import Empty

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            txn = (
                db.query(Transaction)
                .filter(Transaction.id == request.transaction_id, Transaction.user_id == user_id)
                .first()
            )

            if not txn:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Transaction not found")
                return Empty()

            if hasattr(txn, 'card_id'):
                txn.card_id = request.card_id if hasattr(request, 'card_id') else ""
            db.commit()

            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error setting transaction card: {str(e)}")
            return Empty()
        finally:
            db.close()

    def CancelTransaction(self, request, context):
        db = self._get_db()
        try:
            from google.protobuf.empty_pb2 import Empty
            from datetime import datetime

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            txn = (
                db.query(Transaction)
                .filter(Transaction.id == request.transaction_id, Transaction.user_id == user_id)
                .first()
            )

            if not txn:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Transaction not found")
                return Empty()

            txn.status = "cancelled"
            txn.updated_at = datetime.utcnow()
            db.commit()

            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error cancelling transaction: {str(e)}")
            return Empty()
        finally:
            db.close()

    def GetStripeData(self, request, context):
        try:
            return pens_agl_store_pb2.StripeKeysResponse(
                publishable_key="pk_test_placeholder",
                account_id=""
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting Stripe data: {str(e)}")
            return pens_agl_store_pb2.StripeKeysResponse()

    def GetTransactionStripeData(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.TransactionStripeDataResponse()

            return pens_agl_store_pb2.TransactionStripeDataResponse(
                client_secret="pi_placeholder_secret",
                status="requires_payment_method"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting transaction Stripe data: {str(e)}")
            return pens_agl_store_pb2.TransactionStripeDataResponse()

    def SetSaveCard(self, request, context):
        try:
            from google.protobuf.empty_pb2 import Empty

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            save = request.save if hasattr(request, 'save') else False
            logger.info(f"User {user_id} set save card: {save}")
            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error setting save card: {str(e)}")
            return Empty()

    def SetPending(self, request, context):
        db = self._get_db()
        try:
            from google.protobuf.empty_pb2 import Empty
            from datetime import datetime

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            txn = (
                db.query(Transaction)
                .filter(
                    Transaction.id == request.transaction_id,
                    Transaction.user_id == user_id
                )
                .first()
            )

            if txn:
                txn.status = "pending"
                txn.updated_at = datetime.utcnow()
                db.commit()

            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error setting pending: {str(e)}")
            return Empty()
        finally:
            db.close()

    # =====================================================================
    # Vending Methods
    # =====================================================================

    def GetVendingStatus(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.VendingStatusResponse()

            return pens_agl_store_pb2.VendingStatusResponse(
                status="ok",
                can_take_payments=False,
                needs_attention=False
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting vending status: {str(e)}")
            return pens_agl_store_pb2.VendingStatusResponse()

    def StartOnboarding(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.VendingRedirectResponse()

            return pens_agl_store_pb2.VendingRedirectResponse(
                target_url="https://connect.stripe.com/setup/placeholder"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error starting onboarding: {str(e)}")
            return pens_agl_store_pb2.VendingRedirectResponse()

    def GetDashboardLink(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.VendingRedirectResponse()

            return pens_agl_store_pb2.VendingRedirectResponse(
                target_url="https://dashboard.stripe.com/placeholder"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting dashboard link: {str(e)}")
            return pens_agl_store_pb2.VendingRedirectResponse()

    def GetGlobalVendingConfig(self, request, context):
        try:
            return pens_agl_store_pb2.VendingConfigResponse(
                fee_fixed_cost=0,
                fee_cost_percent=0,
                fee_prefer_percent=0
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting global vending config: {str(e)}")
            return pens_agl_store_pb2.VendingConfigResponse()

    def GetAppVendingSetup(self, request, context):
        db = self._get_db()
        try:
            app_id = request.app_id if hasattr(request, 'app_id') else ""
            app = db.query(App).filter(App.id == app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.VendingSetupResponse()

            return pens_agl_store_pb2.VendingSetupResponse(
                app_id=app_id,
                recommended_donation=0,
                minimum_payment=0,
                currency="USD"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting app vending setup: {str(e)}")
            return pens_agl_store_pb2.VendingSetupResponse()
        finally:
            db.close()

    def PostAppVendingSetup(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.VendingSetupResponse()

            app_id = request.app_id if hasattr(request, 'app_id') else ""
            logger.info(f"User {user_id} updating vending setup for {app_id}")

            return pens_agl_store_pb2.VendingSetupResponse(
                app_id=app_id,
                recommended_donation=request.recommended_donation if hasattr(request, 'recommended_donation') else 0,
                minimum_payment=request.minimum_payment if hasattr(request, 'minimum_payment') else 0,
                currency="USD"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error posting app vending setup: {str(e)}")
            return pens_agl_store_pb2.VendingSetupResponse()

    def PostAppVendingStatus(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.VendingOutputResponse()

            return pens_agl_store_pb2.VendingOutputResponse(
                app_id=request.app_id if hasattr(request, 'app_id') else "",
                status="ok"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error posting app vending status: {str(e)}")
            return pens_agl_store_pb2.VendingOutputResponse()

    def GetRedeemableTokens(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.TokenListResponse()

            return pens_agl_store_pb2.TokenListResponse(tokens=[])
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting redeemable tokens: {str(e)}")
            return pens_agl_store_pb2.TokenListResponse()

    def CreateTokens(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.CreateTokensResponse()

            import uuid
            token_names = [str(uuid.uuid4()) for _ in range(request.count if hasattr(request, 'count') else 1)]
            return pens_agl_store_pb2.CreateTokensResponse(
                tokens=token_names,
                status="created"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error creating tokens: {str(e)}")
            return pens_agl_store_pb2.CreateTokensResponse()

    def CancelTokens(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.CancelTokensResponse()

            token_ids = list(request.token_ids) if hasattr(request, 'token_ids') else []
            logger.info(f"Cancelling tokens: {token_ids}")
            return pens_agl_store_pb2.CancelTokensResponse(status="cancelled")
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error cancelling tokens: {str(e)}")
            return pens_agl_store_pb2.CancelTokensResponse()

    def RedeemToken(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.RedemptionResultResponse()

            token = request.token if hasattr(request, 'token') else ""
            logger.info(f"User {user_id} redeeming token: {token}")
            return pens_agl_store_pb2.RedemptionResultResponse(
                status="redeemed",
                app_id=""
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error redeeming token: {str(e)}")
            return pens_agl_store_pb2.RedemptionResultResponse()

    def GetAppInfo(self, request, context):
        db = self._get_db()
        try:
            app_id = request.app_id if hasattr(request, 'app_id') else ""
            app = db.query(App).filter(App.id == app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.VendingApplicationInformationResponse()

            return pens_agl_store_pb2.VendingApplicationInformationResponse(
                app_id=app.id,
                name=app.name,
                developer_name=app.developer_name or "",
                is_free_software=app.is_free_license,
                is_setup=False,
                recommended_donation=0,
                minimum_payment=0
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting app info: {str(e)}")
            return pens_agl_store_pb2.VendingApplicationInformationResponse()
        finally:
            db.close()

    # =====================================================================
    # Verification Methods
    # =====================================================================

    def GetVerificationStatus(self, request, context):
        db = self._get_db()
        try:
            app_id = request.app_id if hasattr(request, 'app_id') else ""
            app = db.query(App).filter(App.id == app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.VerificationStatusResponse()

            return pens_agl_store_pb2.VerificationStatusResponse(
                verified=app.verification_verified,
                method=app.verification_method or "",
                login_name=app.verification_login_name or "",
                login_provider=app.verification_login_provider or "",
                login_is_organization=app.verification_login_is_organization,
                website=app.verification_website or "",
                timestamp=app.verification_timestamp.isoformat() if app.verification_timestamp else ""
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting verification status: {str(e)}")
            return pens_agl_store_pb2.VerificationStatusResponse()
        finally:
            db.close()

    def GetAvailableMethods(self, request, context):
        db = self._get_db()
        try:
            app_id = request.app_id if hasattr(request, 'app_id') else ""
            app = db.query(App).filter(App.id == app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.AvailableMethodsResponse()

            methods = [
                pens_agl_store_pb2.VerificationMethod(
                    method="login_provider",
                    name="Login Provider",
                    description="Verify through your login provider"
                ),
                pens_agl_store_pb2.VerificationMethod(
                    method="website",
                    name="Website",
                    description="Verify through a token on your website"
                )
            ]

            return pens_agl_store_pb2.AvailableMethodsResponse(methods=methods)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting available methods: {str(e)}")
            return pens_agl_store_pb2.AvailableMethodsResponse()
        finally:
            db.close()

    def VerifyByLoginProvider(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.VerifyByLoginProviderResponse()

            from datetime import datetime
            app_id = request.app_id if hasattr(request, 'app_id') else ""
            app = db.query(App).filter(App.id == app_id).first()
            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.VerifyByLoginProviderResponse()

            login_provider = request.login_provider if hasattr(request, 'login_provider') else ""
            app.verification_verified = True
            app.verification_method = "login_provider"
            app.verification_login_provider = login_provider
            app.verification_timestamp = datetime.utcnow()
            db.commit()

            return pens_agl_store_pb2.VerifyByLoginProviderResponse(
                verified=True,
                detail="Verification successful"
            )
        except Exception as e:
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error verifying by login provider: {str(e)}")
            return pens_agl_store_pb2.VerifyByLoginProviderResponse()
        finally:
            db.close()

    def RequestOrganizationAccessGithub(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.LinkResponse()

            return pens_agl_store_pb2.LinkResponse(
                link="https://github.com/settings/connections/applications/GITHUB_CLIENT_ID"
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error requesting organization access: {str(e)}")
            return pens_agl_store_pb2.LinkResponse()

    def SetupWebsiteVerification(self, request, context):
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.WebsiteVerificationTokenResponse()

            import uuid
            token = str(uuid.uuid4())
            app_id = request.app_id if hasattr(request, 'app_id') else ""

            return pens_agl_store_pb2.WebsiteVerificationTokenResponse(
                token=token,
                app_id=app_id
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error setting up website verification: {str(e)}")
            return pens_agl_store_pb2.WebsiteVerificationTokenResponse()

    def ConfirmWebsiteVerification(self, request, context):
        db = self._get_db()
        try:
            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return pens_agl_store_pb2.WebsiteVerificationResultResponse()

            from datetime import datetime
            app_id = request.app_id if hasattr(request, 'app_id') else ""
            app = db.query(App).filter(App.id == app_id).first()

            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return pens_agl_store_pb2.WebsiteVerificationResultResponse()

            # In real implementation, would check token on website
            app.verification_verified = True
            app.verification_method = "website"
            app.verification_website = request.website if hasattr(request, 'website') else ""
            app.verification_timestamp = datetime.utcnow()
            db.commit()

            return pens_agl_store_pb2.WebsiteVerificationResultResponse(
                verified=True,
                detail="Website verification successful"
            )
        except Exception as e:
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error confirming website verification: {str(e)}")
            return pens_agl_store_pb2.WebsiteVerificationResultResponse()
        finally:
            db.close()

    def Unverify(self, request, context):
        db = self._get_db()
        try:
            from google.protobuf.empty_pb2 import Empty

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            app_id = request.app_id if hasattr(request, 'app_id') else ""
            app = db.query(App).filter(App.id == app_id).first()

            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return Empty()

            app.verification_verified = False
            app.verification_method = None
            app.verification_login_name = None
            app.verification_login_provider = None
            app.verification_login_is_organization = False
            app.verification_website = None
            app.verification_timestamp = None
            db.commit()

            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error unverifying: {str(e)}")
            return Empty()
        finally:
            db.close()

    def SwitchToDirectUpload(self, request, context):
        try:
            from google.protobuf.empty_pb2 import Empty

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            app_id = request.app_id if hasattr(request, 'app_id') else ""
            logger.info(f"User {user_id} switching app {app_id} to direct upload")
            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error switching to direct upload: {str(e)}")
            return Empty()

    def Archive(self, request, context):
        db = self._get_db()
        try:
            from google.protobuf.empty_pb2 import Empty

            user_id = self._get_user_id_from_context(context)
            if not user_id:
                context.set_code(grpc.StatusCode.UNAUTHENTICATED)
                context.set_details("Not authenticated")
                return Empty()

            app_id = request.app_id if hasattr(request, 'app_id') else ""
            app = db.query(App).filter(App.id == app_id).first()

            if not app:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("App not found")
                return Empty()

            # Mark app as archived
            if hasattr(app, 'is_archived'):
                app.is_archived = True
                db.commit()
            else:
                logger.info(f"Archiving app {app_id}")

            return Empty()
        except Exception as e:
            from google.protobuf.empty_pb2 import Empty
            db.rollback()
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error archiving app: {str(e)}")
            return Empty()
        finally:
            db.close()

    # =====================================================================
    # Collection Methods
    # =====================================================================

    def GetSubcategory(self, request, context):
        db = self._get_db()
        try:
            category = request.category if hasattr(request, 'category') else ""
            subcategory = request.subcategory if hasattr(request, 'subcategory') else ""
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            query = db.query(App)
            if category:
                query = query.join(App.categories).filter(Category.name == category)
            # Subcategory filtering would use a subcategory field/table in real implementation
            if subcategory:
                query = query.filter(App.summary.ilike(f"%{subcategory}%"))

            total_hits = query.count()
            total_pages = (total_hits + per_page - 1) // per_page if per_page else 1
            apps = query.offset(offset).limit(per_page).all()

            hits = [self._convert_to_apps_index(app) for app in apps]

            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query="",
                hits_per_page=per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting subcategory: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    def GetKeyword(self, request, context):
        db = self._get_db()
        try:
            keyword = request.keyword if hasattr(request, 'keyword') else ""
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            query = db.query(App)
            if keyword:
                query = query.filter(
                    or_(
                        App.name.ilike(f"%{keyword}%"),
                        App.summary.ilike(f"%{keyword}%"),
                        App.description.ilike(f"%{keyword}%")
                    )
                )

            total_hits = query.count()
            total_pages = (total_hits + per_page - 1) // per_page if per_page else 1
            apps = query.offset(offset).limit(per_page).all()

            hits = [self._convert_to_apps_index(app) for app in apps]

            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query=keyword,
                hits_per_page=per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting keyword: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    def GetDevelopers(self, request, context):
        db = self._get_db()
        try:
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            developers = (
                db.query(App.developer_name)
                .filter(App.developer_name.isnot(None))
                .distinct()
                .offset(offset)
                .limit(per_page)
                .all()
            )

            developer_names = [dev.developer_name for dev in developers if dev.developer_name]

            return pens_agl_store_pb2.DevelopersResponse(developers=developer_names)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting developers: {str(e)}")
            return pens_agl_store_pb2.DevelopersResponse()
        finally:
            db.close()

    def GetDeveloper(self, request, context):
        db = self._get_db()
        try:
            developer = request.developer if hasattr(request, 'developer') else ""
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            query = db.query(App)
            if developer:
                query = query.filter(App.developer_name == developer)

            total_hits = query.count()
            total_pages = (total_hits + per_page - 1) // per_page if per_page else 1
            apps = query.offset(offset).limit(per_page).all()

            hits = [self._convert_to_apps_index(app) for app in apps]

            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query=developer,
                hits_per_page=per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting developer apps: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    def GetRecentlyAdded(self, request, context):
        db = self._get_db()
        try:
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            query = db.query(App).order_by(desc(App.added_at))

            total_hits = query.count()
            total_pages = (total_hits + per_page - 1) // per_page if per_page else 1
            apps = query.offset(offset).limit(per_page).all()

            hits = [self._convert_to_apps_index(app) for app in apps]

            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query="",
                hits_per_page=per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting recently added: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    def GetVerified(self, request, context):
        db = self._get_db()
        try:
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            query = db.query(App).filter(App.verification_verified == True).order_by(desc(App.updated_at))

            total_hits = query.count()
            total_pages = (total_hits + per_page - 1) // per_page if per_page else 1
            apps = query.offset(offset).limit(per_page).all()

            hits = [self._convert_to_apps_index(app) for app in apps]

            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query="",
                hits_per_page=per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting verified apps: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    def GetMobile(self, request, context):
        db = self._get_db()
        try:
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            query = db.query(App).filter(App.is_mobile_friendly == True).order_by(desc(App.updated_at))

            total_hits = query.count()
            total_pages = (total_hits + per_page - 1) // per_page if per_page else 1
            apps = query.offset(offset).limit(per_page).all()

            hits = [self._convert_to_apps_index(app) for app in apps]

            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query="",
                hits_per_page=per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting mobile apps: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    def GetPopularLastMonth(self, request, context):
        db = self._get_db()
        try:
            from datetime import datetime, timedelta
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            one_month_ago = datetime.utcnow() - timedelta(days=30)

            # Get apps ordered by installs in last month
            query = (
                db.query(App)
                .outerjoin(AppStats, App.id == AppStats.app_id)
                .filter(
                    or_(
                        AppStats.date >= one_month_ago,
                        AppStats.date.is_(None)
                    )
                )
                .group_by(App.id)
                .order_by(desc(func.coalesce(func.sum(AppStats.installs), 0)))
            )

            total_hits = query.count()
            total_pages = (total_hits + per_page - 1) // per_page if per_page else 1
            apps = query.offset(offset).limit(per_page).all()

            hits = [self._convert_to_apps_index(app) for app in apps]

            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query="",
                hits_per_page=per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting popular last month: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    def GetTrendingLastTwoWeeks(self, request, context):
        db = self._get_db()
        try:
            from datetime import datetime, timedelta
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            two_weeks_ago = datetime.utcnow() - timedelta(days=14)

            # Get apps with most growth in installs over last two weeks
            query = (
                db.query(App)
                .outerjoin(AppStats, App.id == AppStats.app_id)
                .filter(
                    or_(
                        AppStats.date >= two_weeks_ago,
                        AppStats.date.is_(None)
                    )
                )
                .group_by(App.id)
                .order_by(desc(func.coalesce(func.sum(AppStats.installs), 0)))
            )

            total_hits = query.count()
            total_pages = (total_hits + per_page - 1) // per_page if per_page else 1
            apps = query.offset(offset).limit(per_page).all()

            hits = [self._convert_to_apps_index(app) for app in apps]

            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query="",
                hits_per_page=per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting trending last two weeks: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()

    def GetMostFavorited(self, request, context):
        db = self._get_db()
        try:
            page = request.page or 1
            per_page = request.per_page or 21
            offset = (page - 1) * per_page

            # Get apps ordered by number of favorites
            query = (
                db.query(App)
                .outerjoin(Favorite, App.id == Favorite.app_id)
                .group_by(App.id)
                .order_by(desc(func.count(Favorite.id)))
            )

            total_hits = query.count()
            total_pages = (total_hits + per_page - 1) // per_page if per_page else 1
            apps = query.offset(offset).limit(per_page).all()

            hits = [self._convert_to_apps_index(app) for app in apps]

            return pens_agl_store_pb2.SearchAppsResponse(
                hits=hits,
                query="",
                hits_per_page=per_page,
                page=page,
                total_pages=total_pages,
                total_hits=total_hits
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Error getting most favorited: {str(e)}")
            return pens_agl_store_pb2.SearchAppsResponse()
        finally:
            db.close()