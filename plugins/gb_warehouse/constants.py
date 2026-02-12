# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (Constants)

GB_API_URL_TMPL = "https://gamebanana.com/apiv11/Game/8552/Subfeed?_sSort=default&_csvModelInclusions=Mod&_nPage={page}"
GB_MOD_API_TMPL = "https://gamebanana.com/apiv11/Mod/{mod_id}/ProfilePage"

LIST_THUMB_W = 350
LIST_THUMB_H = 200

RESIZE_DEBOUNCE_MS = 500
UI_RESIZE_PAUSED = False

DETAIL_TEXT_WRAP_PAD = 32
DETAIL_TEXT_FUDGE = 12

DOWNLOAD_WRAP_SIDE = 25
DOWNLOAD_TEXT_FUDGE = 0

# Layout sizing (pixels)
LAYOUT_FULL_W = 1280
LIST_BASE_W = 750
LIST_MAX_W = 1000
DETAIL_BASE_W = 300
DOWNLOAD_W = 220

__all__ = [
    "GB_API_URL_TMPL",
    "GB_MOD_API_TMPL",
    "LIST_THUMB_W",
    "LIST_THUMB_H",
    "RESIZE_DEBOUNCE_MS",
    "UI_RESIZE_PAUSED",
    "DETAIL_TEXT_WRAP_PAD",
    "DETAIL_TEXT_FUDGE",
    "DOWNLOAD_WRAP_SIDE",
    "DOWNLOAD_TEXT_FUDGE",
    "LAYOUT_FULL_W",
    "LIST_BASE_W",
    "LIST_MAX_W",
    "DETAIL_BASE_W",
    "DOWNLOAD_W",
]
