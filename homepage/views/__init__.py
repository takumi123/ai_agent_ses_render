from .base import (
    index, google_login, google_callback, logout_view,
    video_list, video_upload, video_detail, video_status,
    review_list, analyze_with_gemini, bulk_process_videos,
    user_list, analyze_unprocessed_videos, update_video_thumbnails,
    authorize
)

from .admin.users import (
    user_list as admin_user_list,
    user_toggle_admin,
    user_delete,
    user_videos
)

from .admin.videos import (
    video_list as admin_video_list,
    video_upload as admin_video_upload,
    video_delete as admin_video_delete,
    video_analyze
)

from .admin.categories import (
    category_list,
    category_add,
    category_edit,
    category_delete,
    category_reorder,
    subcategory_add,
    subcategory_edit,
    subcategory_delete,
    subcategory_reorder
)

from .admin import dashboard
