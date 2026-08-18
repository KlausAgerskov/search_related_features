# -*- coding: utf-8 -*-
"""
translation.py
--------------
Loading of translations.

The source language is English: the strings in the code are what gets shown
when no translation exists. Danish sits in i18n/search_related_features_da.qm and
is loaded at start-up.

The language is chosen in this order:

    1. the plugin's own setting, if it is set
    2. the language QGIS is actually running in
    3. the system language

Changing language requires the plugin to be reloaded - which is why the choice
lives in QgsSettings and not in the project.

Translations are compiled from .ts to .qm with lrelease:

    lrelease i18n/search_related_features_da.ts

The .qm files must be in the zip; without them everything falls back to
English.
"""

import os

from qgis.PyQt.QtCore import QCoreApplication, QTranslator, QLocale
from qgis.core import QgsSettings, QgsApplication, Qgis

from .project_config import log

LANGUAGE_SETTING = "search_related_features/language"

# Languages there are translations for. The source language has no .qm file.
AVAILABLE = [
    ("", u"Follow QGIS"),
    ("en", u"English"),
    ("da", u"Dansk"),
]

# The translator has to be kept alive here. Bound only to a local variable,
# Python collects it again and Qt is left with a dead translator - everything
# reverts to English without any error.
_translator = None


def language():
    """The language the user picked. An empty string means: follow QGIS."""
    return QgsSettings().value(LANGUAGE_SETTING, u"", type=str)


def set_language(code):
    """Store the language choice. Takes effect when the plugin is reloaded."""
    QgsSettings().setValue(LANGUAGE_SETTING, code or u"")


def qgis_language():
    """The language QGIS effectively runs in, as a two-letter code.

    QgsApplication.locale() is the right source, because it accounts for
    whether "Override system locale" is switched on or off.

    Reading locale/userLocale directly gives the value stored in the settings
    dialog - even when the check box is off and QGIS is in fact running in the
    system language. Switch the override off after having had English selected,
    and the key still says "en", so the plugin would be English even though
    QGIS is Danish.
    """
    code = u""
    try:
        code = QgsApplication.locale() or u""
    except (AttributeError, TypeError):      # very old QGIS versions
        code = u""

    if not code:
        settings = QgsSettings()
        if settings.value("locale/overrideFlag", False, type=bool):
            code = settings.value("locale/userLocale", u"", type=str)
    if not code:
        code = QLocale.system().name()
    return (code or u"en")[:2]


def resolve_language():
    """The two-letter code to actually use."""
    chosen = language()
    if chosen:
        return chosen[:2]
    return qgis_language()


def plugin_root():
    """The plugin folder itself. This module sits in core/, so i18n/ is one
    level up - taking dirname(__file__) alone would look inside core/."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def qm_path(code):
    return os.path.join(plugin_root(), "i18n",
                        "search_related_features_{}.qm".format(code))


def install_translator():
    """Load the translation for the chosen language.

    Called from classFactory, that is before any widget exists: a string that
    has already been translated does not get translated again.
    """
    global _translator                       # pylint: disable=global-statement

    code = resolve_language()
    if code == "en":                         # source language, nothing to load
        log(u"Language: en (source language, no translation loaded)")
        return False

    path = qm_path(code)
    if not os.path.exists(path):
        # the usual cause: the .ts file was never compiled with lrelease, or
        # the i18n folder did not make it into the zip
        log(u"Language: {} requested, but {} is missing - falling back to "
            u"English. Run: lrelease i18n/search_related_features_{}.ts".format(
                code, os.path.basename(path), code), Qgis.Warning)
        return False

    translator = QTranslator()
    if not translator.load(path):
        log(u"Language: {} found at {} but could not be loaded".format(
            code, path), Qgis.Warning)
        return False

    QCoreApplication.installTranslator(translator)
    _translator = translator
    log(u"Language: {} loaded from {}".format(code, os.path.basename(path)))
    return True


def report():
    """Where the language choice lands, and why. For the Python console.

        from search_related_features.translation import report
        print(report())
    """
    settings = QgsSettings()
    code = resolve_language()
    path = qm_path(code)
    return {
        "plugin setting": language() or u"(not set, follows QGIS)",
        "QgsApplication.locale()": QgsApplication.locale(),
        "locale/overrideFlag": settings.value(
            "locale/overrideFlag", False, type=bool),
        "locale/userLocale": settings.value("locale/userLocale", u"", type=str),
        "system locale": QLocale.system().name(),
        "resolved": code,
        "qm file": path,
        "qm exists": os.path.exists(path),
    }


def tr(text, context="SearchRelatedFeatures"):
    """Translate a string outside a QObject.

    Inside a QObject use self.tr() instead - it sets the class name as the
    context, and that is what pylupdate writes into the .ts file.
    """
    return QCoreApplication.translate(context, text)
