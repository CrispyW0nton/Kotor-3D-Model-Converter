from __future__ import annotations

from enum import Enum
from typing import Union

from qtpy.QtCore import Qt
from qtpy.QtGui import QAction, QIcon, QKeySequence


class ActionKey(Enum):
    OPEN = "open"
    OPEN_AS_ADMIN = "open_as_admin"
    OPEN_IN_NEW_WINDOW = "open_in_new_window"
    OPEN_IN_NEW_TAB = "open_in_new_tab"
    OPEN_WITH = "open_with"
    PROPERTIES = "properties"
    OPEN_TERMINAL = "open_terminal"
    OPEN_IN_TERMINAL = "open_in_terminal"
    TAKE_OWNERSHIP = "take_ownership"
    ADD_TO_ARCHIVE = "add_to_archive"
    CUT = "cut"
    COPY = "copy"
    PASTE = "paste"
    COPY_PATH = "copy_path"
    COPY_AS_PATH = "copy_as_path"
    PASTE_SHORTCUT = "paste_shortcut"
    CREATE_SHORTCUT = "create_shortcut"
    MOVE_TO = "move_to"
    COPY_TO = "copy_to"
    DELETE = "delete"
    RENAME = "rename"
    PIN_TO_QUICK_ACCESS = "pin_to_quick_access"
    NEW_FOLDER = "new_folder"
    NEW_BLANK_FILE = "new_blank_file"
    NEW_TEXT_DOCUMENT = "new_text_document"
    NEW_COMPRESSED_FOLDER = "new_compressed_folder"
    NEW_SHORTCUT = "new_shortcut"
    EDIT = "edit"
    SELECT_ALL = "select_all"
    SELECT_NONE = "select_none"
    INVERT_SELECTION = "invert_selection"
    EXTRA_LARGE_ICONS = "extra_large_icons"
    LARGE_ICONS = "large_icons"
    MEDIUM_ICONS = "medium_icons"
    SMALL_ICONS = "small_icons"
    LIST_VIEW = "list_view"
    DETAIL_VIEW = "detail_view"
    TILES = "tiles"
    CONTENT = "content"
    NAVIGATION_PANE = "navigation_pane"
    PREVIEW_PANE = "preview_pane"
    DETAILS_PANE = "details_pane"
    SHOW_HIDDEN_FILES = "show_hidden_files"
    SHOW_HIDE_HIDDEN_ITEMS = "show_hide_hidden_items"
    SHOW_FILE_EXTENSIONS = "show_file_extensions"
    SHOW_ITEM_CHECKBOXES = "show_item_checkboxes"
    SORT_BY_NAME = "sort_by_name"
    SORT_BY_DATE = "sort_by_date"
    SORT_BY_DATE_MODIFIED = "sort_by_date_modified"
    SORT_BY_DATE_CREATED = "sort_by_date_created"
    SORT_BY_TYPE = "sort_by_type"
    SORT_BY_SIZE = "sort_by_size"
    SORT_BY_AUTHOR = "sort_by_author"
    SORT_BY_TAGS = "sort_by_tags"
    SORT_ASCENDING = "sort_ascending"
    SORT_DESCENDING = "sort_descending"
    GROUP_BY_NONE = "group_by_none"
    GROUP_BY_NAME = "group_by_name"
    GROUP_BY_DATE = "group_by_date"
    GROUP_BY_DATE_CREATED = "group_by_date_created"
    GROUP_BY_DATE_MODIFIED = "group_by_date_modified"
    GROUP_BY_TYPE = "group_by_type"
    GROUP_BY_SIZE = "group_by_size"
    SHARE = "share"
    EMAIL = "email"
    COMPRESS_TO_ZIP = "compress_to_zip"
    COMPRESS = "compress"
    EXTRACT = "extract"
    SEND_TO_DESKTOP = "send_to_desktop"
    SEND_TO_DOCUMENTS = "send_to_documents"
    SEND_TO_COMPRESSED_FOLDER = "send_to_compressed_folder"
    PRINT = "print"
    BURN_TO_DISC = "burn_to_disc"
    GO_BACK = "go_back"
    GO_FORWARD = "go_forward"
    GO_UP = "go_up"
    REFRESH = "refresh"
    OPTIONS = "options"
    FOLDER_OPTIONS = "folder_options"
    PERSONALIZE = "personalize"
    DISPLAY_SETTINGS = "display_settings"
    CUSTOMIZE_CONTEXT_MENU = "customize_context_menu"
    DUPLICATE_FINDER = "duplicate_finder"
    HASH_GENERATOR = "hash_generator"
    PERMISSIONS_EDITOR = "permissions_editor"
    FILE_SHREDDER = "file_shredder"
    FILE_COMPARISON = "file_comparison"
    UNDO = "undo"
    REDO = "redo"


ShortcutType = Union[QKeySequence, QKeySequence.StandardKey, Qt.Key, str, None]


class ActionDefinition:
    """Declarative definition for a file explorer action.

    This class provides a structured way to define QAction configurations
    for file explorer/browser applications. Each definition includes:
    - icon: Theme icon name (freedesktop.org icon naming spec)
    - text: User-visible text for the action
    - shortcut: Keyboard shortcut (Qt.Key, QKeySequence.StandardKey, or string)
    - operation: Name of async operation to perform
    - prepare_func: Name of function to prepare operation parameters
    - handler_func: Name of direct handler function (for sync operations)
    - async_operation: Whether the operation runs asynchronously
    - checkable: Whether the action has a toggle state
    - checked: Default checked state if checkable
    - extra_kwargs: Additional keyword arguments for handlers
    """

    def __init__(
        self,
        icon: str,
        text: str,
        shortcut: ShortcutType = None,
        operation: str | None = None,
        prepare_func: str | None = None,
        handler_func: str | None = None,
        async_operation: bool = True,
        checkable: bool = False,
        checked: bool = False,
        **kwargs: object,
    ):
        self.icon: str = icon
        self.text: str = text
        self.shortcut: ShortcutType = shortcut
        self.operation: str | None = operation
        self.prepare_func: str | None = prepare_func
        self.handler_func: str | None = handler_func
        self.async_operation: bool = async_operation
        self.checkable: bool = checkable
        self.checked: bool = checked
        self.extra_kwargs: dict[str, object] = kwargs


class FileExplorerActions:
    """Creates actions for a file browser/manager/explorer using declarative definitions.

    This class provides a centralized registry of all actions used by file explorer
    widgets. Actions are defined declaratively in ACTION_DEFINITIONS and created
    on initialization.

    Access actions via:
    - actionPropertyName - via @property accessors for backward compatibility

    All action properties are explicitly defined (no __getattr__) for static type checking.
    """

    # =============================================================================
    # DECLARATIVE ACTION DEFINITIONS
    # =============================================================================

    # Each ActionDefinition specifies a QAction's complete configuration.
    # Actions are grouped by category for organization.

    ACTION_DEFINITIONS: dict[ActionKey, ActionDefinition] = {
        # =========================================================================
        # OPEN ACTIONS
        # Actions related to opening files, folders, and running programs
        # =========================================================================
        ActionKey.OPEN: ActionDefinition("document-open", "Open", QKeySequence.StandardKey.Open, "open_file", async_operation=True),
        ActionKey.OPEN_AS_ADMIN: ActionDefinition("dialog-password", "Open as Administrator", "Ctrl+Shift+A", "open_as_admin"),
        ActionKey.OPEN_IN_NEW_WINDOW: ActionDefinition("window-new", "Open in New Window", "Ctrl+Enter", "open_in_new_window"),
        ActionKey.OPEN_IN_NEW_TAB: ActionDefinition("tab-new", "Open in New Tab", "Alt+Enter", "open_in_new_tab"),
        ActionKey.OPEN_WITH: ActionDefinition("document-open", "Open With...", "Alt+O", "open_with"),
        ActionKey.PROPERTIES: ActionDefinition("document-properties", "Properties", "Alt+Return", "get_properties"),
        ActionKey.OPEN_TERMINAL: ActionDefinition("utilities-terminal", "Open Terminal", "Shift+F10", "open_terminal"),
        ActionKey.OPEN_IN_TERMINAL: ActionDefinition("utilities-terminal", "Open in Terminal", "Ctrl+Shift+T", "open_terminal", prepare_func="prepare_open_in_terminal"),
        # =========================================================================
        # EDIT / CLIPBOARD ACTIONS
        # Cut, copy, paste and related clipboard operations
        # =========================================================================
        ActionKey.CUT: ActionDefinition("edit-cut", "Cut", QKeySequence.StandardKey.Cut, None, handler_func="on_cut_items"),
        ActionKey.COPY: ActionDefinition("edit-copy", "Copy", QKeySequence.StandardKey.Copy, None, handler_func="on_copy_items"),
        ActionKey.PASTE: ActionDefinition("edit-paste", "Paste", QKeySequence.StandardKey.Paste, None, handler_func="on_paste_items"),
        ActionKey.COPY_PATH: ActionDefinition("edit-copy", "Copy Path", "Ctrl+Shift+C", None, handler_func="copy_path"),
        ActionKey.COPY_AS_PATH: ActionDefinition("edit-copy", "Copy as path", None, None, handler_func="copy_as_path"),
        ActionKey.PASTE_SHORTCUT: ActionDefinition("insert-link", "Paste Shortcut", "Ctrl+Shift+V", None, handler_func="paste_shortcut"),
        ActionKey.CREATE_SHORTCUT: ActionDefinition("insert-link", "Create Shortcut", None, "create_shortcut"),
        # =========================================================================
        # ORGANIZE ACTIONS
        # Move, copy to, delete, rename operations
        # =========================================================================
        ActionKey.MOVE_TO: ActionDefinition("edit-cut", "Move To...", "F6", None, handler_func="move_to"),
        ActionKey.COPY_TO: ActionDefinition("edit-copy", "Copy To...", None, None, handler_func="copy_to"),
        ActionKey.DELETE: ActionDefinition("edit-delete", "Delete", QKeySequence.StandardKey.Delete, "delete_items"),
        ActionKey.RENAME: ActionDefinition("edit-rename", "Rename", Qt.Key.Key_F2, "rename_item"),
        ActionKey.PIN_TO_QUICK_ACCESS: ActionDefinition("bookmark-new", "Pin to Quick access", "Ctrl+Q", None, handler_func="pin_to_quick_access"),
        # =========================================================================
        # NEW ITEMS ACTIONS
        # Creating new folders, files, shortcuts
        # =========================================================================
        ActionKey.NEW_FOLDER: ActionDefinition("folder-new", "New folder", "Ctrl+Shift+N", "new_folder", prepare_func="prepare_new_folder"),
        ActionKey.NEW_BLANK_FILE: ActionDefinition("document-new", "New Blank File", "Ctrl+N", "new_file", prepare_func="prepare_new_file"),
        ActionKey.NEW_TEXT_DOCUMENT: ActionDefinition("document-new", "New Text Document", None, "new_text_document"),
        ActionKey.NEW_COMPRESSED_FOLDER: ActionDefinition("package-x-generic", "New Compressed Folder", None, "new_compressed_folder"),
        ActionKey.NEW_SHORTCUT: ActionDefinition("insert-link", "New Shortcut", None, "new_shortcut"),
        # =========================================================================
        # EDIT ACTIONS
        # File editing operations
        # =========================================================================
        ActionKey.EDIT: ActionDefinition("document-edit", "Edit", None, None, handler_func="edit_file"),
        # =========================================================================
        # SELECT ACTIONS
        # Selection management operations
        # =========================================================================
        ActionKey.SELECT_ALL: ActionDefinition("edit-select-all", "Select All", QKeySequence.StandardKey.SelectAll, None, handler_func="select_all"),
        ActionKey.SELECT_NONE: ActionDefinition("edit-select-none", "Select None", "Escape", None, handler_func="select_none"),
        ActionKey.INVERT_SELECTION: ActionDefinition("edit-select-all", "Invert Selection", "Ctrl+I", None, handler_func="invert_selection"),
        # =========================================================================
        # VIEW MODE ACTIONS
        # Icon sizes and view layouts (matches Windows Explorer View tab)
        # =========================================================================
        ActionKey.EXTRA_LARGE_ICONS: ActionDefinition(
            "view-list-icons", "Extra large icons", "Ctrl+Shift+1", None, handler_func="set_view_mode", checkable=True, extra_kwargs={"mode": "extra_large"}
        ),
        ActionKey.LARGE_ICONS: ActionDefinition(
            "view-list-icons", "Large icons", "Ctrl+Shift+2", None, handler_func="set_view_mode", checkable=True, extra_kwargs={"mode": "large"}
        ),
        ActionKey.MEDIUM_ICONS: ActionDefinition(
            "view-list-icons", "Medium icons", "Ctrl+Shift+3", None, handler_func="set_view_mode", checkable=True, extra_kwargs={"mode": "medium"}
        ),
        ActionKey.SMALL_ICONS: ActionDefinition(
            "view-list-icons", "Small icons", "Ctrl+Shift+4", None, handler_func="set_view_mode", checkable=True, extra_kwargs={"mode": "small"}
        ),
        ActionKey.LIST_VIEW: ActionDefinition("view-list-details", "List", "Ctrl+Shift+5", None, handler_func="set_view_mode", checkable=True, extra_kwargs={"mode": "list"}),
        ActionKey.DETAIL_VIEW: ActionDefinition(
            "view-list-tree", "Details", "Ctrl+Shift+6", None, handler_func="set_view_mode", checkable=True, extra_kwargs={"mode": "detail"}
        ),
        ActionKey.TILES: ActionDefinition("view-list-icons", "Tiles", "Ctrl+Shift+7", None, handler_func="set_view_mode", checkable=True, extra_kwargs={"mode": "tiles"}),
        ActionKey.CONTENT: ActionDefinition("view-list-text", "Content", "Ctrl+Shift+8", None, handler_func="set_view_mode", checkable=True, extra_kwargs={"mode": "content"}),
        # =========================================================================
        # PANES ACTIONS
        # Navigation pane, preview pane, details pane toggles
        # =========================================================================
        ActionKey.NAVIGATION_PANE: ActionDefinition(
            "view-sidetree", "Navigation Pane", "Ctrl+Shift+E", None, handler_func="toggle_navigation_pane", checkable=True, checked=True
        ),
        ActionKey.PREVIEW_PANE: ActionDefinition("view-preview", "Preview Pane", "Alt+P", None, handler_func="toggle_preview_pane", checkable=True),
        ActionKey.DETAILS_PANE: ActionDefinition("view-list-tree", "Details Pane", "Alt+Shift+P", None, handler_func="toggle_details_pane", checkable=True),
        # =========================================================================
        # SHOW/HIDE ACTIONS
        # Toggle visibility of hidden files, extensions, etc.
        # =========================================================================
        ActionKey.SHOW_HIDDEN_FILES: ActionDefinition("view-hidden", "Hidden Items", "Ctrl+H", None, handler_func="toggle_hidden_files", checkable=True),
        ActionKey.SHOW_HIDE_HIDDEN_ITEMS: ActionDefinition("view-hidden", "Show/Hide Hidden Items", "Ctrl+H", None, handler_func="toggle_hidden_items", checkable=True),
        ActionKey.SHOW_FILE_EXTENSIONS: ActionDefinition(
            "view-list-details", "File Name Extensions", None, None, handler_func="toggle_file_extensions", checkable=True, checked=True
        ),
        ActionKey.SHOW_ITEM_CHECKBOXES: ActionDefinition("checkbox", "Item Check Boxes", None, None, handler_func="toggle_item_checkboxes", checkable=True),
        # =========================================================================
        # SORT ACTIONS
        # Sorting options matching Windows Explorer
        # =========================================================================
        ActionKey.SORT_BY_NAME: ActionDefinition("view-sort", "Name", None, None, handler_func="sort_by_name", checkable=True, checked=True),
        ActionKey.SORT_BY_DATE: ActionDefinition("view-sort", "Date modified", None, None, handler_func="sort_by_date", checkable=True),
        ActionKey.SORT_BY_DATE_MODIFIED: ActionDefinition("view-sort", "Date modified", None, None, handler_func="sort_by_date_modified", checkable=True),
        ActionKey.SORT_BY_DATE_CREATED: ActionDefinition("view-sort", "Date created", None, None, handler_func="sort_by_date_created", checkable=True),
        ActionKey.SORT_BY_TYPE: ActionDefinition("view-sort", "Type", None, None, handler_func="sort_by_type", checkable=True),
        ActionKey.SORT_BY_SIZE: ActionDefinition("view-sort", "Size", None, None, handler_func="sort_by_size", checkable=True),
        ActionKey.SORT_BY_AUTHOR: ActionDefinition("view-sort", "Author", None, None, handler_func="sort_by_author", checkable=True),
        ActionKey.SORT_BY_TAGS: ActionDefinition("view-sort", "Tags", None, None, handler_func="sort_by_tags", checkable=True),
        ActionKey.SORT_ASCENDING: ActionDefinition("view-sort-ascending", "Ascending", None, None, handler_func="sort_ascending", checkable=True, checked=True),
        ActionKey.SORT_DESCENDING: ActionDefinition("view-sort-descending", "Descending", None, None, handler_func="sort_descending", checkable=True),
        # =========================================================================
        # GROUP ACTIONS
        # Grouping options
        # =========================================================================
        ActionKey.GROUP_BY_NONE: ActionDefinition("view-list-text", "None", None, None, handler_func="group_by_none", checkable=True, checked=True),
        ActionKey.GROUP_BY_NAME: ActionDefinition("view-list-text", "Name", None, None, handler_func="group_by_name", checkable=True),
        ActionKey.GROUP_BY_DATE: ActionDefinition("view-list-text", "Date modified", None, None, handler_func="group_by_date", checkable=True),
        ActionKey.GROUP_BY_DATE_CREATED: ActionDefinition("view-list-text", "Date created", None, None, handler_func="group_by_date_created", checkable=True),
        ActionKey.GROUP_BY_DATE_MODIFIED: ActionDefinition("view-list-text", "Date modified", None, None, handler_func="group_by_date_modified", checkable=True),
        ActionKey.GROUP_BY_TYPE: ActionDefinition("view-list-text", "Type", None, None, handler_func="group_by_type", checkable=True),
        ActionKey.GROUP_BY_SIZE: ActionDefinition("view-list-text", "Size", None, None, handler_func="group_by_size", checkable=True),
        # =========================================================================
        # SHARE TAB ACTIONS
        # Share, email, compress, print
        # =========================================================================
        ActionKey.SHARE: ActionDefinition("emblem-shared", "Share", None, None, handler_func="share_items"),
        ActionKey.EMAIL: ActionDefinition("mail-send", "Email", None, None, handler_func="email_items"),
        ActionKey.COMPRESS_TO_ZIP: ActionDefinition("package-x-generic", "Compress to ZIP file", None, "compress_to_zip"),
        ActionKey.COMPRESS: ActionDefinition("package-x-generic", "Compress", None, "compress"),
        ActionKey.EXTRACT: ActionDefinition("extract-archive", "Extract", None, "extract"),
        ActionKey.SEND_TO_DESKTOP: ActionDefinition("document-send", "Send to Desktop", None, "send_to_desktop"),
        ActionKey.SEND_TO_DOCUMENTS: ActionDefinition("document-send", "Send to Documents", None, "send_to_documents"),
        ActionKey.SEND_TO_COMPRESSED_FOLDER: ActionDefinition("document-send", "Send to Compressed Folder", None, "send_to_compressed_folder"),
        ActionKey.TAKE_OWNERSHIP: ActionDefinition("document-edit-sign", "Take Ownership", None, "take_ownership"),
        ActionKey.ADD_TO_ARCHIVE: ActionDefinition("package-x-generic", "Add to Archive", None, "add_to_archive"),
        ActionKey.PRINT: ActionDefinition("document-print", "Print", QKeySequence.StandardKey.Print, None, handler_func="print_items"),
        ActionKey.BURN_TO_DISC: ActionDefinition("media-optical-burn", "Burn to disc", None, "burn_to_disc"),
        # =========================================================================
        # NAVIGATION ACTIONS
        # Back, forward, up, refresh
        # =========================================================================
        ActionKey.GO_BACK: ActionDefinition("go-previous", "Back", QKeySequence.StandardKey.Back, None, handler_func="go_back"),
        ActionKey.GO_FORWARD: ActionDefinition("go-next", "Forward", QKeySequence.StandardKey.Forward, None, handler_func="go_forward"),
        ActionKey.GO_UP: ActionDefinition("go-up", "Up", "Alt+Up", None, handler_func="go_up"),
        ActionKey.REFRESH: ActionDefinition("view-refresh", "Refresh", QKeySequence.StandardKey.Refresh, None, handler_func="refresh_view"),
        # =========================================================================
        # OPTIONS/SETTINGS ACTIONS
        # Configuration dialogs
        # =========================================================================
        ActionKey.OPTIONS: ActionDefinition("configure", "Options...", "Ctrl+,", None, handler_func="show_options"),
        ActionKey.FOLDER_OPTIONS: ActionDefinition("folder-open", "Folder Options", None, None, handler_func="show_folder_options"),
        ActionKey.PERSONALIZE: ActionDefinition("preferences-system", "Personalize", None, "personalize"),
        ActionKey.DISPLAY_SETTINGS: ActionDefinition("preferences-system-display", "Display Settings", None, "display_settings"),
        ActionKey.CUSTOMIZE_CONTEXT_MENU: ActionDefinition("configure", "Customize Context Menu", "Ctrl+Shift+X", None, handler_func="prepare_customize_context_menu"),
        # =========================================================================
        # ADVANCED UTILITY ACTIONS
        # Power user features
        # =========================================================================
        ActionKey.DUPLICATE_FINDER: ActionDefinition("edit-find-replace", "Find Duplicate Files", "Ctrl+Shift+D", "find_duplicates", prepare_func="prepare_duplicate_finder"),
        ActionKey.HASH_GENERATOR: ActionDefinition("document-encrypt", "Generate File Hashes", "Ctrl+Shift+H", "generate_hashes", prepare_func="prepare_hash_generator"),
        ActionKey.PERMISSIONS_EDITOR: ActionDefinition("document-edit-sign", "Edit File Permissions", None, "edit_permissions", prepare_func="prepare_permissions_editor"),
        ActionKey.FILE_SHREDDER: ActionDefinition("edit-delete-shred", "Securely Delete Files", "Ctrl+Shift+Del", "shred_files", prepare_func="prepare_file_shredder"),
        ActionKey.FILE_COMPARISON: ActionDefinition("document-compare", "Compare Files", "Ctrl+Shift+M", "compare_files", prepare_func="prepare_file_comparison"),
        # =========================================================================
        # UNDO/REDO ACTIONS
        # =========================================================================
        ActionKey.UNDO: ActionDefinition("edit-undo", "Undo", QKeySequence.StandardKey.Undo, None, handler_func="undo"),
        ActionKey.REDO: ActionDefinition("edit-redo", "Redo", QKeySequence.StandardKey.Redo, None, handler_func="redo"),
    }

    def __init__(self):
        self.actions: dict[ActionKey, QAction] = {}
        self._create_actions()

    def _create_actions(self):
        """Create QAction instances from declarative definitions."""
        for key, definition in self.ACTION_DEFINITIONS.items():
            action = QAction(QIcon.fromTheme(definition.icon), definition.text)
            action.setObjectName(key.value)
            if definition.shortcut:
                if isinstance(definition.shortcut, str):
                    action.setShortcut(QKeySequence(definition.shortcut))
                elif isinstance(definition.shortcut, (QKeySequence.StandardKey, Qt.Key)):
                    action.setShortcut(QKeySequence(definition.shortcut))
                else:
                    action.setShortcut(definition.shortcut)
            if definition.checkable:
                action.setCheckable(True)
                if definition.checked:
                    action.setChecked(True)
            self.actions[key] = action

    # Backward compatibility properties for old action names
    @property
    def actionOpen(self) -> QAction:
        return self.actions[ActionKey.OPEN]

    @property
    def actionOpenAsAdmin(self) -> QAction:
        return self.actions[ActionKey.OPEN_AS_ADMIN]

    @property
    def actionOpenInNewWindow(self) -> QAction:
        return self.actions[ActionKey.OPEN_IN_NEW_WINDOW]

    @property
    def actionOpenInNewTab(self) -> QAction:
        return self.actions[ActionKey.OPEN_IN_NEW_TAB]

    @property
    def actionOpenWith(self) -> QAction:
        return self.actions[ActionKey.OPEN_WITH]

    @property
    def actionProperties(self) -> QAction:
        return self.actions[ActionKey.PROPERTIES]

    @property
    def actionOpenTerminal(self) -> QAction:
        return self.actions[ActionKey.OPEN_TERMINAL]

    @property
    def actionCut(self) -> QAction:
        return self.actions[ActionKey.CUT]

    @property
    def actionCopy(self) -> QAction:
        return self.actions[ActionKey.COPY]

    @property
    def actionPaste(self) -> QAction:
        return self.actions[ActionKey.PASTE]

    @property
    def actionDelete(self) -> QAction:
        return self.actions[ActionKey.DELETE]

    @property
    def actionRename(self) -> QAction:
        return self.actions[ActionKey.RENAME]

    @property
    def actionPinToQuickAccess(self) -> QAction:
        return self.actions[ActionKey.PIN_TO_QUICK_ACCESS]

    @property
    def actionCopyPath(self) -> QAction:
        return self.actions[ActionKey.COPY_PATH]

    @property
    def actionCopyAsPath(self) -> QAction:
        return self.actions[ActionKey.COPY_AS_PATH]

    @property
    def actionPasteShortcut(self) -> QAction:
        return self.actions[ActionKey.PASTE_SHORTCUT]

    @property
    def actionCreateShortcut(self) -> QAction:
        return self.actions[ActionKey.CREATE_SHORTCUT]

    @property
    def actionMoveTo(self) -> QAction:
        return self.actions[ActionKey.MOVE_TO]

    @property
    def actionCopyTo(self) -> QAction:
        return self.actions[ActionKey.COPY_TO]

    @property
    def actionCreateNewFolder(self) -> QAction:
        return self.actions[ActionKey.NEW_FOLDER]

    @property
    def actionEdit(self) -> QAction:
        return self.actions[ActionKey.EDIT]

    @property
    def actionSelectAll(self) -> QAction:
        return self.actions[ActionKey.SELECT_ALL]

    @property
    def actionSelectNone(self) -> QAction:
        return self.actions[ActionKey.SELECT_NONE]

    @property
    def actionInvertSelection(self) -> QAction:
        return self.actions[ActionKey.INVERT_SELECTION]

    @property
    def actionNavigationPane(self) -> QAction:
        return self.actions[ActionKey.NAVIGATION_PANE]

    @property
    def actionPreviewPane(self) -> QAction:
        return self.actions[ActionKey.PREVIEW_PANE]

    @property
    def actionDetailsPane(self) -> QAction:
        return self.actions[ActionKey.DETAILS_PANE]

    @property
    def actionExtraLargeIcons(self) -> QAction:
        return self.actions[ActionKey.EXTRA_LARGE_ICONS]

    @property
    def actionLargeIcons(self) -> QAction:
        return self.actions[ActionKey.LARGE_ICONS]

    @property
    def actionMediumIcons(self) -> QAction:
        return self.actions[ActionKey.MEDIUM_ICONS]

    @property
    def actionSmallIcons(self) -> QAction:
        return self.actions[ActionKey.SMALL_ICONS]

    @property
    def actionListView(self) -> QAction:
        return self.actions[ActionKey.LIST_VIEW]

    @property
    def actionDetailView(self) -> QAction:
        return self.actions[ActionKey.DETAIL_VIEW]

    @property
    def actionTiles(self) -> QAction:
        return self.actions[ActionKey.TILES]

    @property
    def actionContent(self) -> QAction:
        return self.actions[ActionKey.CONTENT]

    @property
    def actionOptions(self) -> QAction:
        return self.actions[ActionKey.OPTIONS]

    # =========================================================================
    # SHOW/HIDE ACTION PROPERTIES
    # =========================================================================

    @property
    def actionShowHiddenFiles(self) -> QAction:
        return self.actions[ActionKey.SHOW_HIDDEN_FILES]

    @property
    def actionShowHideHiddenItems(self) -> QAction:
        return self.actions[ActionKey.SHOW_HIDE_HIDDEN_ITEMS]

    @property
    def actionShowFileExtensions(self) -> QAction:
        return self.actions[ActionKey.SHOW_FILE_EXTENSIONS]

    @property
    def actionShowItemCheckboxes(self) -> QAction:
        return self.actions[ActionKey.SHOW_ITEM_CHECKBOXES]

    # =========================================================================
    # SORT ACTION PROPERTIES
    # =========================================================================

    @property
    def actionSortByName(self) -> QAction:
        return self.actions[ActionKey.SORT_BY_NAME]

    @property
    def actionSortByDate(self) -> QAction:
        return self.actions[ActionKey.SORT_BY_DATE]

    @property
    def actionSortByDateModified(self) -> QAction:
        return self.actions[ActionKey.SORT_BY_DATE_MODIFIED]

    @property
    def actionSortByDateCreated(self) -> QAction:
        return self.actions[ActionKey.SORT_BY_DATE_CREATED]

    @property
    def actionSortByType(self) -> QAction:
        return self.actions[ActionKey.SORT_BY_TYPE]

    @property
    def actionSortBySize(self) -> QAction:
        return self.actions[ActionKey.SORT_BY_SIZE]

    @property
    def actionSortByAuthor(self) -> QAction:
        return self.actions[ActionKey.SORT_BY_AUTHOR]

    @property
    def actionSortByTags(self) -> QAction:
        return self.actions[ActionKey.SORT_BY_TAGS]

    @property
    def actionSortAscending(self) -> QAction:
        return self.actions[ActionKey.SORT_ASCENDING]

    @property
    def actionSortDescending(self) -> QAction:
        return self.actions[ActionKey.SORT_DESCENDING]

    # =========================================================================
    # GROUP ACTION PROPERTIES
    # =========================================================================

    @property
    def actionGroupByNone(self) -> QAction:
        return self.actions[ActionKey.GROUP_BY_NONE]

    @property
    def actionGroupByName(self) -> QAction:
        return self.actions[ActionKey.GROUP_BY_NAME]

    @property
    def actionGroupByDate(self) -> QAction:
        return self.actions[ActionKey.GROUP_BY_DATE]

    @property
    def actionGroupByDateCreated(self) -> QAction:
        return self.actions[ActionKey.GROUP_BY_DATE_CREATED]

    @property
    def actionGroupByDateModified(self) -> QAction:
        return self.actions[ActionKey.GROUP_BY_DATE_MODIFIED]

    @property
    def actionGroupByType(self) -> QAction:
        return self.actions[ActionKey.GROUP_BY_TYPE]

    @property
    def actionGroupBySize(self) -> QAction:
        return self.actions[ActionKey.GROUP_BY_SIZE]

    # =========================================================================
    # SHARE TAB ACTION PROPERTIES
    # =========================================================================

    @property
    def actionShare(self) -> QAction:
        return self.actions[ActionKey.SHARE]

    @property
    def actionEmail(self) -> QAction:
        return self.actions[ActionKey.EMAIL]

    @property
    def actionCompressToZip(self) -> QAction:
        return self.actions[ActionKey.COMPRESS_TO_ZIP]

    @property
    def actionCompress(self) -> QAction:
        return self.actions[ActionKey.COMPRESS]

    @property
    def actionExtract(self) -> QAction:
        return self.actions[ActionKey.EXTRACT]

    @property
    def actionSendToDesktop(self) -> QAction:
        return self.actions[ActionKey.SEND_TO_DESKTOP]

    @property
    def actionSendToDocuments(self) -> QAction:
        return self.actions[ActionKey.SEND_TO_DOCUMENTS]

    @property
    def actionSendToCompressedFolder(self) -> QAction:
        return self.actions[ActionKey.SEND_TO_COMPRESSED_FOLDER]

    @property
    def actionTakeOwnership(self) -> QAction:
        return self.actions[ActionKey.TAKE_OWNERSHIP]

    @property
    def actionAddToArchive(self) -> QAction:
        return self.actions[ActionKey.ADD_TO_ARCHIVE]

    @property
    def actionPrint(self) -> QAction:
        return self.actions[ActionKey.PRINT]

    @property
    def actionBurnToDisc(self) -> QAction:
        return self.actions[ActionKey.BURN_TO_DISC]

    # =========================================================================
    # NAVIGATION ACTION PROPERTIES
    # =========================================================================

    @property
    def actionGoBack(self) -> QAction:
        return self.actions[ActionKey.GO_BACK]

    @property
    def actionGoForward(self) -> QAction:
        return self.actions[ActionKey.GO_FORWARD]

    @property
    def actionGoUp(self) -> QAction:
        return self.actions[ActionKey.GO_UP]

    @property
    def actionRefresh(self) -> QAction:
        return self.actions[ActionKey.REFRESH]

    # =========================================================================
    # NEW ITEM ACTION PROPERTIES
    # =========================================================================

    @property
    def actionNewFolder(self) -> QAction:
        return self.actions[ActionKey.NEW_FOLDER]

    @property
    def actionNewBlankFile(self) -> QAction:
        return self.actions[ActionKey.NEW_BLANK_FILE]

    @property
    def actionNewTextDocument(self) -> QAction:
        return self.actions[ActionKey.NEW_TEXT_DOCUMENT]

    @property
    def actionNewCompressedFolder(self) -> QAction:
        return self.actions[ActionKey.NEW_COMPRESSED_FOLDER]

    @property
    def actionNewShortcut(self) -> QAction:
        return self.actions[ActionKey.NEW_SHORTCUT]

    # =========================================================================
    # UNDO/REDO ACTION PROPERTIES
    # =========================================================================

    @property
    def actionUndo(self) -> QAction:
        return self.actions[ActionKey.UNDO]

    @property
    def actionRedo(self) -> QAction:
        return self.actions[ActionKey.REDO]

    # =========================================================================
    # ADVANCED UTILITY ACTION PROPERTIES
    # =========================================================================

    @property
    def actionDuplicateFinder(self) -> QAction:
        return self.actions[ActionKey.DUPLICATE_FINDER]

    @property
    def actionHashGenerator(self) -> QAction:
        return self.actions[ActionKey.HASH_GENERATOR]

    @property
    def actionPermissionsEditor(self) -> QAction:
        return self.actions[ActionKey.PERMISSIONS_EDITOR]

    @property
    def actionFileShredder(self) -> QAction:
        return self.actions[ActionKey.FILE_SHREDDER]

    @property
    def actionFileComparison(self) -> QAction:
        return self.actions[ActionKey.FILE_COMPARISON]

    @property
    def actionOpenInTerminal(self) -> QAction:
        return self.actions[ActionKey.OPEN_IN_TERMINAL]

    @property
    def actionFolderOptions(self) -> QAction:
        return self.actions[ActionKey.FOLDER_OPTIONS]

    @property
    def actionPersonalize(self) -> QAction:
        return self.actions[ActionKey.PERSONALIZE]

    @property
    def actionDisplaySettings(self) -> QAction:
        return self.actions[ActionKey.DISPLAY_SETTINGS]

    @property
    def actionCustomizeContextMenu(self) -> QAction:
        return self.actions[ActionKey.CUSTOMIZE_CONTEXT_MENU]
