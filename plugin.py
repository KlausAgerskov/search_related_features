# -*- coding: utf-8 -*-
"""
plugin.py
---------
The main class. Creates the toolbar and menu entries, owns the search panel,
and makes sure the setup is reloaded when a new project is opened.
"""

import os

from qgis.PyQt.QtCore import Qt, QObject
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsProject, Qgis

try:
    from qgis.PyQt import sip
except ImportError:                           # older PyQt versions
    import sip

from .gui.search_panel import SearchPanel
from .gui.config_dialog import ConfigDialog
from .core.project_config import log, resolve_layer

MENU_NAME = u"&Search Related Features"
TOOLBAR_NAME = u"Search Related Features"


def delete_now(obj):
    """Delete a Qt object right away.

    deleteLater() is deferred to the next pass of the event loop. Plugin
    Reloader checks for leftover widgets immediately after unload(), and so
    still finds both the toolbar and the panel, with the warning "removing
    duplicated widget(s) not cleaned up by the plugin during unload".
    sip.delete() tears the object down now and makes the cleanup visible to the
    reloader.
    """
    if obj is None:
        return
    try:
        if not sip.isdeleted(obj):
            sip.delete(obj)
    except (RuntimeError, TypeError, ValueError, AttributeError):
        try:
            obj.deleteLater()
        except RuntimeError:
            pass


class SearchRelatedFeatures(QObject):
    """QGIS plugin: search tables and select the related polygons."""

    def __init__(self, iface):
        # deliberately without a parent: were the plugin a child of the main
        # window, the old instance would survive every reload
        super(SearchRelatedFeatures, self).__init__()
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.panel = None
        self.toolbar = None
        self.actionPanel = None
        self.actionSettings = None
        self._panel_was_visible = False

    # -- building the GUI --------------------------------------------------

    def _icon(self, filename):
        return QIcon(os.path.join(self.plugin_dir, "images", filename))

    def _add_action(self, icon, text, callback, checkable=False, tooltip=None):
        action = QAction(icon, text, self.iface.mainWindow())
        action.setCheckable(checkable)
        if checkable:
            action.toggled.connect(callback)
        else:
            action.triggered.connect(callback)
        if tooltip:
            action.setToolTip(tooltip)
            action.setStatusTip(tooltip)
        self.toolbar.addAction(action)
        self.iface.addPluginToDatabaseMenu(MENU_NAME, action)
        self.actions.append(action)
        return action

    def initGui(self):
        self.toolbar = self.iface.addToolBar(TOOLBAR_NAME)
        self.toolbar.setObjectName("SearchRelatedFeaturesToolbar")

        self.panel = SearchPanel(self.iface, self.iface.mainWindow())
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.panel)
        self.panel.hide()

        self.actionPanel = self._add_action(
            self._icon("icon.svg"),
            self.tr("Search and select"),
            self._toggle_panel,
            checkable=True,
            tooltip=self.tr("Show the search panel"))
        self.panel.visibilityChanged.connect(self._panel_visibility_changed)

        self.actionSettings = self._add_action(
            self._icon("settings.svg"),
            self.tr("Settings"),
            self._show_settings,
            tooltip=self.tr("Edit which tables and layers are linked"))

        # reload the setup when a project opens, and close the panel when the
        # current project is cleared
        self.iface.projectRead.connect(self._project_read)
        self.iface.newProjectCreated.connect(self._project_cleared)
        QgsProject.instance().cleared.connect(self._project_cleared)

        # the plugin may have been loaded after the project
        if QgsProject.instance().mapLayers():
            self.panel.reload()

    def unload(self):
        """Remove everything the plugin put into the user interface.

        The order matters: signals are disconnected first, so nothing is called
        on half-demolished objects, and each widget is removed from the main
        window before it is deleted, so the main window is not left holding a
        dead child reference.
        """
        for signal, slot in ((self.iface.projectRead, self._project_read),
                             (self.iface.newProjectCreated, self._project_cleared),
                             (QgsProject.instance().cleared, self._project_cleared)):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass

        # the panel
        if self.panel is not None:
            try:
                self.panel.visibilityChanged.disconnect(
                    self._panel_visibility_changed)
            except (TypeError, RuntimeError):
                pass
            try:
                self.panel.teardown()
            except RuntimeError:
                pass
            self.iface.removeDockWidget(self.panel)
            self.panel.setParent(None)
            delete_now(self.panel)
            self.panel = None

        # menu entries and actions
        for action in self.actions:
            self.iface.removePluginDatabaseMenu(MENU_NAME, action)
            self.iface.removeToolBarIcon(action)
            if self.toolbar is not None:
                self.toolbar.removeAction(action)
            action.setParent(None)
            delete_now(action)
        self.actions = []
        self.actionPanel = None
        self.actionSettings = None

        # the toolbar. removeToolBar() takes it out of the main window layout
        # but leaves the main window as its parent, so it must be deleted too
        if self.toolbar is not None:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.setParent(None)
            delete_now(self.toolbar)
            self.toolbar = None

    # -- actions -----------------------------------------------------------

    def _toggle_panel(self, checked):
        if self.panel is None:
            return
        self.panel.setUserVisible(checked)

    def _panel_visibility_changed(self, visible):
        """Keep the toolbar button in sync with the visibility of the panel."""
        if self.actionPanel is None or sip.isdeleted(self.actionPanel):
            return
        if self.actionPanel.isChecked() != visible:
            self.actionPanel.blockSignals(True)
            self.actionPanel.setChecked(visible)
            self.actionPanel.blockSignals(False)

    def _project_cleared(self):
        """The project was closed or cleared: empty and close the panel.

        The visibility is remembered, because QGIS also clears the old project
        when a new one is opened. If a project is opened right afterwards, the
        panel is put back the way the user had it.
        """
        if self.panel is None:
            return
        self._panel_was_visible = self.panel.isUserVisible()
        self.panel.reload()
        self.panel.setUserVisible(False)

    def _project_read(self):
        """A project was opened: reload, and restore the panel visibility."""
        if self.panel is None:
            return
        self.panel.reload()
        if self._panel_was_visible:
            self.panel.setUserVisible(True)
        self._panel_was_visible = False

    def _show_settings(self):
        dialog = ConfigDialog(self.iface.mainWindow())
        if dialog.exec_():
            if self.panel is not None:
                self.panel.reload()
            self.iface.messageBar().pushMessage(
                u"Search Related Features",
                self.tr("The setup is saved in the project. Remember to "
                        "save the project."),
                level=Qgis.Info, duration=6)
