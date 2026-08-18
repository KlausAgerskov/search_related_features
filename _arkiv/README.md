# Search Related Features

*[Dansk version](README.da.md)*

QGIS plugin. Run a free-text search on an attribute table without geometry and
have the related polygons selected in the map.

The plugin is not tied to particular layers or field names. The setup is defined
in a dialog and stored in the project, so it travels with the project file or
the project template. If a project has no stored setup, the plugin derives one
automatically from the relations of the project.

A typical use: a table without geometry holds cases, measures or registrations,
where each row points at a polygon through a shared key field. One table can
point at several polygon layers — for instance when the geometries are split
across layers — and the plugin then selects in whichever layers match.

## Installation

Install the zip through *Plugins > Manage and Install Plugins > Install from
ZIP*. Build the zip with:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

It lands in `build\`. Do not zip the folder by hand: the `.qm` files are not in
Git, and a zip without them falls back to English with no error message.

During development, deploy straight into a QGIS profile instead:

```powershell
.\build.ps1 -Deploy                 # the "default" profile
.\build.ps1 -Deploy -Profile NST    # another profile
```

Then reload with Plugin Reloader.

## Use

1. Open the project.
2. Click **Search and select** in the toolbar.
3. Pick a table in the drop-down, narrow it down with free text and column
   filters.
4. Select individual rows, or click **Select filtered rows** for all of them.
5. The related polygons are selected in the map.

**Buttons and fields**

| Element | What it does |
|---|---|
| Drop-down at the top | Pick the table to search in |
| Free-text search | Several words are combined with AND, searched in all shown columns, regardless of order |
| Pre-filter | Collapsible box: an expression that cuts rows away already when the table is fetched |
| Add filter column | Add a column filter, see below |
| Reset | Remove all column filters, keep the free-text search |
| *X of Y rows shown* | How much the filters have cut away |
| Select filtered rows (N) | Select the polygons for every shown row at once. The rows are selected in the panel and in the table layer at the same time |
| Zoom | Zoom to the selected polygons. If the selection spans several layers, the extents are combined |
| Activate layer | Make the target layer the active layer |
| Follow map selection | The other direction: select polygons in the map, and the matching rows are highlighted in the table |
| Clear | Clear search, value choices and selections. The column filters stay |

### The selection follows the table layer

The row selection in the panel is not merely visual: the same rows are selected
in the table layer itself. This holds for all three routes — rows selected by
hand, **Select filtered rows** (which selects every shown row) and **Follow map
selection**.

Everything that works on the layer selection therefore works:

- The QGIS attribute table shows the same rows as selected, including under
  *Show Selected Features*.
- Right-click the table layer > *Export > Save Selected Features As* exports
  exactly the selection the panel shows — for instance a filtered extract to
  Excel or GeoPackage.
- Expressions using `is_selected()` and processing tools with *Selected features
  only* hit the same set.

**Clear** removes the selection in both the table layer and the target layers.

### Column filters

Pick a column under **Add filter column** and click **Add**. You get a drop-down
with check boxes and the values that actually occur in the column, with the row
count in brackets. Several columns can be filtered at once:

| | Combination |
|---|---|
| Several values in the **same** column | OR |
| Filters on **different** columns | AND |
| Free text on top | AND |

The value lists **cascade**: each drop-down only shows the values that are still
possible once the other filters are applied, and the counts update as you go. A
column's own drop-down does not narrow itself, so a choice can always be widened
again. The drop-down does not close on a click, so several values can be checked
in one go.

At the top of every drop-down sits **(select all)**. One click checks every
value, so the few you do not want can be cleared afterwards — far fewer clicks
than checking twenty values one at a time. Click it again to clear them all. The
check box shows a partial mark when only some values are selected, and the
closed drop-down reads `all (N)` when the whole list is checked.

Empty values are shown as `(empty)` and sort last. Numeric columns sort
numerically, so 9 comes before 10 and 100.

### Pre-filter

The **Pre-filter** box at the top of the panel holds the expression that limits
which rows are fetched at all — for instance `"Status" < 100` to work only with
rows that are not finished. It is the same setting as in the settings dialog,
but it can be adjusted while you work:

| Button | Effect |
|---|---|
| Apply | Fetch the table again with the expression. This session only |
| Clear | Fetch all rows again |
| Save in the project | Make the expression the default for the configuration. Remember to save the project |

The title changes to "Pre-filter (active)" when an expression is in use, so it
is visible even when the box is collapsed. The pre-filter differs from the other
filters by working on the data source: the rows are never fetched. Free text and
column filters work on the rows already loaded.

### Remembered column filters

Which columns you filter on is remembered for the next time the panel is used —
but **only the columns, not the value choices**, so the panel always opens with
every row visible. If you always use the same two columns, their drop-downs are
ready immediately.

This is stored in QgsSettings for the user, not in the project file, since it is
a working habit rather than a property of the project. Two colleagues can
therefore have their own setup in the same project. The key is the layer id of
the table, so each configuration is remembered separately, and renaming changes
nothing.

The **Clear** button clears the value choices but leaves the columns. **Reset**
in the filter row removes them entirely — and thereby forgets them for next
time.

### Value maps

Where a field stores codes rather than text — say `graesning` instead of
"Grazing" — the panel shows the text from the value map of the field in the
table, in the drop-downs and in the button text, while filtering happens on the
stored value. The translation goes through the field formatters of QGIS, the
same mechanism the attribute table uses, so `ValueMap`, `ValueRelation`,
`Range`, `DateTime` and `CheckBox` work without any setup of their own.

Free-text search hits both, so `Grazing` and `graesning` find the same rows. The
tooltip on a cell shows the stored value.

If two codes share the same displayed text, the code is shown in square brackets
in the drop-down, so they can be told apart and filtered separately.

Column headers use the alias of the field where one is set.

Above 500 distinct keys you are asked first, since the selection may take a
moment.

## Settings

The **Settings** button opens the dialog. The *Derive from project relations*
button creates one configuration per table with relations, brings along every
target layer of the relation, and includes every column of the table. If the
table has many fields, trim them afterwards under *Columns*.

For each configuration you pick:

- **Table** — the table to search in. By default only layers without geometry
  are shown; tick *Also show layers with geometry* to search a polygon layer.
- **Key field** — the field to link on.
- **Filter** — an optional expression limiting the rows, for instance
  `"Status" < 100`.
- **Columns** — what is shown and searched. The key field is always included.
  If none is checked, every column of the table is shown.
- **Target layers** — all layers with geometry in the project. Check the ones to
  search, and pick in the column beside it which field in the layer matches the
  key field of the table. **The two fields need not have the same name** — in an
  Esri model they are typically `GlobalID` in the parent and `ParentGlobalId` in
  the child. A field is suggested based on the name, but the suggestion can
  always be changed. Checked layers are searched in order. If a target layer
  from the setup is not loaded right now, it sits at the top marked *(missing
  from the project)* and stays checked, so it is not lost when the setup is
  saved.

The setup is written to the project. **Save the project afterwards**, or it is
lost. Save it in a template, and every derived project inherits it.

### Where the setup lives

As a project property under the scope `search_related_features`, key
`searchConfigs`, serialised as JSON. It ends up in `<properties>` in the `.qgs`
file inside the `.qgz` archive.

To set it up from the console instead:

```python
from search_related_features.project_config import configs_from_relations, save_configs
save_configs(configs_from_relations())
```

### Schema

```json
{
  "name": "<name in the drop-down>",
  "table": "<layer id or layer name>",
  "table_key": "<field name>",
  "search_fields": ["<field name>", "<field name>"],
  "filter_expression": "\"Status\" < 100",
  "targets": [
    {"layer": "<layer id>", "key": "<field name>"},
    {"layer": "<layer id>", "key": "<field name>"}
  ]
}
```

Layers are stored by id and looked up by id first, then by name. A layer can
therefore be renamed without breaking the setup, and a setup can be written by
hand using layer names. An empty `search_fields` means every column.

## Design decisions

**Field names rather than relation ids.** Linking is done on named fields, not
on `QgsRelation.id()`. Delete and recreate a relation and the id changes, which
would leave a stored setup pointing at nothing. The field in the table and the
field in the target layer are chosen separately, so `ParentGlobalId` can point
at `GlobalID`. The field pair is also symmetric, so it does not matter which
side is the parent.

**Two lookup routes.** Where the layers sit on a remote source —
`arcgisfeatureserver`, WFS, a database across the network — both extremes are
expensive: a full index means fetching the whole layer, and an expression per
click calls out to the server every time. The route is therefore chosen by how
many keys are needed:

| Number of keys | Route |
|---|---|
| Up to `EXPRESSION_LIMIT` (200) | `IN (...)` expression straight at the layer, split into portions of 100 |
| Above that, or when the index already exists | `{key: [feature id]}` index, built once per layer per session |

A single click in the table therefore costs one small query rather than a fetch
of the whole layer, while **Select filtered rows** across many rows pays for the
index and gets every later lookup for free. The answers to the direct lookups
are remembered per key, including the empty ones, so the same click twice in a
row costs one query.

Both routes normalise the key again on the answer, since a server may match
case-insensitively. If the expression cannot be carried out, it is logged and
the index is built instead. Both caches are cleared automatically when the layer
is edited, and when a new project is opened.

The timings are logged under *View > Panels > Log Messages >
search_related_features*, so it can be seen which route was used and what it cost.
The constants sit at the top of `key_index.py`; `EXPRESSION_LIMIT = 0` turns the
direct route off.

**Key values are normalised** to trimmed strings, so text/number differences
between the two sides of a relation do not cause silent mismatches. If the key
sits as a GUID with braces in one layer and without in the other, that has to be
handled explicitly in `normalize_key`.

**Silent validation.** Configurations with a missing table or key field are
dropped on load and logged under *View > Panels > Log Messages >
search_related_features*. A half-loaded project therefore gives fewer choices
rather than an error.

A single missing target layer does not drop the configuration: it is skipped
during selection but stays in the setup. Otherwise a layer that happened not to
load one day would be written out of the `.qgz` file the next time the setup was
saved.

## Language

The user interface is English in the source; Danish is delivered as a
translation. The language is chosen in this order:

1. the plugin's own setting, if it is set
2. `QgsApplication.locale()` — the effective language of QGIS
3. the system language

Point 2 deliberately asks QGIS for the language actually in use, rather than
reading `locale/userLocale`. That key holds the language selected in the
settings dialog, even when *Override system locale* is switched off and QGIS is
in fact running in the system language.

Changing language requires the plugin to be reloaded. Live switching is
deliberately not built, since it would require `retranslateUi()` in every dialog
for a setting that rarely changes.

Every user-facing string is translatable: 93 strings across eight contexts
(`FacetFilter`, `CheckableValueCombo`, `FacetWidget`, `FacetBar`,
`SearchRelatedFeatures`, `ProjectConfig`, `ConfigDialog`, `SearchPanel`).

Log messages are not translated. They are for troubleshooting and are easier to
search when they always appear in one language.

### When the language does not take effect

The plugin logs its language choice on load under *View > Panels > Log Messages
> search_related_features*, for instance `Language: da loaded from
search_related_features_da.qm`. If the `.qm` file is missing, a warning gives the
`lrelease` command to run.

The whole decision can be inspected from the console:

```python
import qgis.utils, importlib
name = [n for n in qgis.utils.plugins if "related_features" in n.lower()][0]
tr = importlib.import_module(name + ".translation")
for key, value in tr.report().items():
    print(key, "=", value)
```

### Translating

Pull the strings out of the code and update the `.ts` file:

```
pylupdate5 *.py -ts i18n/search_related_features_da.ts
```

Correct the translations in Qt Linguist, then compile to `.qm`:

```
lrelease i18n/search_related_features_da.ts
```

**Not every QGIS installation ships `lrelease.exe`** — some carry only
`linguist.exe`. That is not a problem: *File > Release* in Qt Linguist produces
exactly the same `.qm` file. To open it with the right environment:

```powershell
.\build.ps1 -Linguist
```

That finds `linguist.exe` inside the QGIS installation and puts the QGIS `bin`
folder on PATH for the process, which is what the `libpng16.dll not found`
error is about when Linguist is started straight from Explorer.

When `lrelease` is missing, `build.ps1` does not compile anything. It checks
instead that a `.qm` exists and is no older than its `.ts`, warns if it is
stale, and fails outright under `-Release`. So a forgotten *File > Release*
cannot slip into a published zip.

The `.qm` files **must be in the zip** — without them everything falls back to
English, with no error message. A new language needs only a new `.ts` file and a
line in `AVAILABLE` in `translation.py`.

### For the developer

User-facing strings are written in English and wrapped:

- inside a `QObject`: `self.tr("Add")` — the class name becomes the context
- outside a `QObject`: `_tr("(empty)")`, which sets the context explicitly

Two traps are worth knowing. **Strings at module level** are evaluated on
import, before the translator is installed — which is why `EMPTY_LABEL` and
`ALL_LABEL` became the functions `empty_label()` and `all_label()`. And
**placeholders must be numbered**, `"{0} selected"` rather than `"{} selected"`,
since word order differs between languages and the translator has to be able to
reorder them.

The user's own data — field names, aliases, the texts of value maps and `name`
in the setup — is not translated.

## Files

```
search_related_features/
├── __init__.py                 classFactory
├── metadata.txt
├── search_related_features.py     main class: toolbar, menu, project hooks
├── search_panel.py             the dock panel: search, filters, selection
├── facet_filter.py             column filters with cascading value lists
├── value_format.py             translates stored codes to displayed text
├── config_dialog.py            settings dialog
├── project_config.py           read/write setup in the project, validation
├── key_index.py                key lookups: IN expression and cached index
├── translation.py              language choice and loading of translations
├── build.ps1                   compiles translations, checks, packages the zip
├── LICENSE                     GPL v2 text
├── i18n/                       .ts sources and compiled .qm files
└── images/
```

## Known limitations

- If the data source cannot translate `IN (...)` into a server call, QGIS
  evaluates the expression locally and pulls the layer through anyway. The
  direct route is then no faster than the index, but no slower either — the
  timings in the log messages show which happened.
- The table is loaded fully into memory and filtered locally. Fine up to some
  tens of thousands of rows. Above that, `_populate` should be reworked into a
  `setFilterExpression` call per search.
- The cascade of the column filters walks every row per active filter. With many
  rows and many simultaneous filters the update can become noticeable; the value
  counts would then need caching per column instead.
- Column filters cannot yet be stored in the setup as a preset. For a fixed
  pre-filter, use `filter_expression` in the settings dialog.
- **Follow map selection** collides with the selection logic in
  SelectByRelationship if both plugins are active on the same relations.
- Qt6 is not supported (`supportsQt6=False`). The unscoped Qt enums, for
  instance `Qt.UserRole` and `QDialogButtonBox.Save`, have to be rewritten into
  the `Qt.ItemDataRole.UserRole` form first.

## Development

### Building

`build.ps1` compiles the translations, checks the metadata, and packages the
zip. It looks for `lrelease.exe` on PATH and then inside the QGIS installation;
if it cannot find it, pass the path in:

```powershell
.\build.ps1 -LReleasePath "C:\Program Files\QGIS 3.44.12\apps\qt5\bin\lrelease.exe"
```

Before publishing, run the release checks:

```powershell
.\build.ps1 -Release
```

That fails the build unless `repository`, `tracker`, `homepage` and `email` are
filled in, `experimental` is `False`, a `LICENSE` file exists, the icon exists,
and the `.qm` files were produced. It also warns about strings still marked
*unfinished* in a `.ts` file — `lrelease` drops those, and they appear in
English.

`.qm` files are build output and are not in Git; the `.ts` files are the source
and are.

### Reloading

When reloading with Plugin Reloader, `unload()` has to tear everything down
immediately. `deleteLater()` is deferred to the next pass of the event loop, and
the reloader checks right after unload — hence `sip.delete()` through
`delete_now()`. If widgets are left behind, the warning appears:

```
WARNING: removing duplicated widget(s) not cleaned up by the plugin
during unload: SearchRelatedFeaturesToolbar, SearchRelatedFeaturesPanel
```

Check in the console that nothing is left after unload:

```python
from qgis.PyQt.QtWidgets import QToolBar, QDockWidget
win = iface.mainWindow()
print([w.objectName() for w in win.findChildren(QToolBar) + win.findChildren(QDockWidget)
       if w.objectName().startswith("SearchRelatedFeatures")])
```

## Licence

GNU General Public License v2 or later.
