# -*- coding: utf-8 -*-
"""
search_related_features
=======================
QGIS plugin by Naturstyrelsen (the Danish Nature Agency).

Search an attribute table without geometry and have the related polygons
selected in the map. The setup is stored in the project file (.qgz), so it
travels with the project template.

The user interface is English, with a Danish translation in i18n/.

Licence: GNU General Public License v2 or later.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Entry point called by QGIS when the plugin is loaded.

    :param iface: QGIS interface instance.
    :type iface: QgisInterface
    """
    # the translation has to be in place before the first widget is created
    from .translation import install_translator
    install_translator()

    from .search_related_features import SearchRelatedFeatures
    return SearchRelatedFeatures(iface)
