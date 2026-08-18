# Search Related Features

*[English version](README.md) — den engelske udgave er hovedudgaven og opdateres først.*

QGIS-plugin til Naturstyrelsen. Fritekstsøg i en attributtabel uden geometri og
få de relaterede polygoner markeret i kortet.

Plugin'et er ikke bundet til bestemte lag eller feltnavne. Opsætningen
defineres i dialogen og gemmes i projektet, så den følger med projektfilen eller
projektskabelonen. Har projektet ingen gemt opsætning, udleder plugin'et den
automatisk af projektets relationer.

Typisk brug: en tabel uden geometri indeholder sager, indsatser eller
registreringer, hvor hver række peger på en polygon via et fælles nøglefelt.
Én tabel kan pege på flere polygonlag — fx hvis geometrierne er delt op — og så
markeres der i de lag der matcher.

## Installation

Zip mappen og installér via *Plugins > Håndtér og installér plugins >
Installér fra ZIP*.

Under udvikling kan mappen i stedet kopieres direkte til profilens
plugin-mappe:

```
%APPDATA%\QGIS\QGIS3\profiles\<profil>\python\plugins\search_related_features\
```

Genindlæs derefter med Plugin Reloader. Zip'en må ikke indeholde `__pycache__`
eller `.git`.

## Brug

1. Åbn projektet.
2. Klik **Søg og vælg** i værktøjslinjen.
3. Vælg tabel i dropdown, indsnævr med fritekst og kolonnefiltre.
4. Markér enkelte rækker, eller klik **Vælg filtrerede rækker** for dem alle.
5. De relaterede polygoner markeres i kortet.

**Knapper og felter**

| Element | Funktion |
|---|---|
| Dropdown øverst | Vælg hvilken tabel der søges i |
| Fritekstsøgning | Flere ord kombineres med OG, søges i alle viste kolonner, uafhængigt af rækkefølge |
| Forfilter | Sammenklappelig boks: udtryk der skærer rækker fra allerede når tabellen hentes |
| Tilføj filtrerings kolonne | Tilføj et kolonnefilter, se nedenfor |
| Nulstil | Fjern alle kolonnefiltre, behold fritekstsøgningen |
| *X af Y rækker vist* | Hvor meget filtrene har skåret væk |
| Vælg filtrerede rækker (N) | Vælg polygonerne for alle viste rækker på én gang. Rækkerne markeres samtidig i panelet og i tabellaget |
| Zoom | Zoom til de markerede polygoner. Rammer markeringen flere lag, samles udstrækningen |
| Aktivér lag | Gør mållaget til aktivt lag |
| Følg kortvalg | Modsat retning: markér polygoner i kortet, og de matchende rækker fremhæves i tabellen |
| Ryd | Ryd søgning, værdivalg og markeringer. Kolonnefiltrene bliver stående |

### Markeringen følger tabellaget

Panelets rækkevalg er ikke kun visuelt: de samme rækker markeres i selve
tabellaget. Det gælder alle tre veje — rækker markeret i hånden, **Vælg
filtrerede rækker** (som markerer alle viste rækker) og **Følg kortvalg**.

Dermed virker alt det der arbejder på lagets markering:

- QGIS' egen attributtabel viser de samme rækker som markerede, også i
  *Vis kun valgte objekter*.
- Højreklik på tabellaget > *Eksportér > Gem valgte objekter som* eksporterer
  netop det udvalg panelet viser — fx et filtreret udtræk til Excel eller
  GeoPackage.
- Udtryk med `is_selected()` og processeringsværktøjer med *Kun valgte objekter*
  rammer det samme udvalg.

**Ryd** fjerner markeringen i både tabellaget og mållagene.

### Kolonnefiltre

Vælg en kolonne i **Tilføj filtrerings kolonne** og klik **Tilføj**. Der kommer
en dropdown med afkrydsningsfelter og de værdier, der faktisk findes i
kolonnen, med antal rækker i parentes. Flere kolonner kan filtreres samtidig:

| | Kombination |
|---|---|
| Flere værdier i **samme** kolonne | ELLER |
| Filtre på **forskellige** kolonner | OG |
| Fritekst oveni | OG |

Værdilisterne er **kaskaderende**: hver dropdown viser kun de værdier der stadig
er mulige, når de øvrige filtre er lagt på, og antallet opdateres løbende. En
kolonnes egen dropdown indsnævrer ikke sig selv, så et valg kan altid udvides
igen. Dropdown'en lukker ikke ved klik, så flere værdier kan krydses af i træk.

Øverst i hver dropdown står **(vælg alle)**. Ét klik krydser alle værdier af, så
de få der ikke skal med kan fravælges bagefter — det er langt færre klik end at
krydse tyve værdier af én ad gangen. Klikkes der igen, fjernes alle fluebenene.
Fluebenet viser med en halv markering at kun nogle af værdierne er valgt, og
den lukkede dropdown skriver `alle (N)`, når hele listen er krydset af.

Tomme værdier vises som `(tom)` og sorteres sidst. Talkolonner sorteres
numerisk, så 9 kommer før 10 og 100.

### Forfilter

Boksen **Forfilter** øverst i panelet indeholder det udtryk, der begrænser
hvilke rækker der overhovedet hentes — fx `"Status" < 100` for kun at arbejde
med rækker der ikke er afsluttet. Det er den samme indstilling som i
opsætningsdialogen, men den kan justeres direkte under arbejdet:

| Knap | Virkning |
|---|---|
| Anvend | Hent tabellen igen med udtrykket. Gælder kun denne session |
| Fjern | Hent alle rækker igen |
| Gem i projektet | Gør udtrykket til standard for opsætningen. Husk at gemme projektet |

Titlen skifter til "Forfilter (aktivt)", når der er et udtryk i brug, så det er
synligt selv når boksen er klappet sammen. Forfilteret adskiller sig fra de
øvrige filtre ved at virke på datakilden: rækkerne bliver ikke hentet. Fritekst
og kolonnefiltre arbejder på de rækker der allerede er indlæst.

### Huskede kolonnefiltre

Hvilke kolonner der filtreres på huskes til næste gang panelet bruges — men
**kun kolonnerne, ikke værdivalgene**, så panelet altid åbner med alle rækker
synlige. Bruger man altid de samme to kolonner, står deres dropdowns klar med
det samme.

Det gemmes i QgsSettings hos brugeren, ikke i projektfilen, da det er en
arbejdsvane snarere end en egenskab ved projektet. To kolleger kan derfor have
hver deres opsætning i det samme projekt. Nøglen er tabellens lag-id, så hver
opsætning huskes for sig, og omdøbning ændrer intet.

Knappen **Ryd** rydder værdivalgene, men lader kolonnerne stå. **Nulstil** i
filterrækken fjerner dem helt — og glemmer dem dermed også til næste gang.

### Værdilister

Gemmer et felt koder frem for tekst — fx `graesning` i stedet for "Græsning" —
viser panelet teksten fra feltets værdiliste i tabellen, i dropdown'ene og i
knapteksten, mens filtreringen sker på den gemte værdi. Oversættelsen sker
gennem QGIS' egne feltformatteringer, altså samme mekanisme som
attributtabellen, så `ValueMap`, `ValueRelation`, `Range`, `DateTime` og
`CheckBox` virker uden særskilt opsætning.

Fritekstsøgning rammer begge dele, så både `Græsning` og `graesning` finder de
samme rækker. Værktøjstip på en celle viser den gemte værdi.

Har to koder samme viste tekst, vises koden i kantet parentes i dropdown'en, så
de kan skelnes og filtreres hver for sig.

Kolonneoverskrifter bruger feltets alias, hvis der er sat et.

Over 500 forskellige nøgler bliver der spurgt først, da markeringen kan tage et
øjeblik.

## Opsætning

**Opsætning**-knappen åbner dialogen. Knappen *Udled fra projektets relationer*
opretter én opsætning pr. tabel med relationer, tager alle relationens mållag
med og medtager alle tabellens kolonner. Har tabellen mange felter, skæres de
til bagefter under *Kolonner*.

For hver opsætning vælges:

- **Tabel** — tabellen der søges i. Som udgangspunkt vises kun lag uden
  geometri; sæt flueben i *Vis også lag med geometri* for at søge i et
  polygonlag.
- **Nøglefelt** — feltet der kædes på.
- **Filter** — valgfrit udtryk der begrænser rækkerne, fx `"Status" < 100`.
- **Kolonner** — hvad der vises og søges i. Nøglefeltet medtages altid. Er
  ingen markeret, vises alle tabellens kolonner.
- **Mållag** — alle lag med geometri i projektet. Markér dem der skal
  gennemsøges, og vælg i kolonnen ved siden af hvilket felt i laget der svarer
  til tabellens nøglefelt. **De to felter behøver ikke hedde det samme** — i en
  Esri-model hedder de typisk `GlobalID` i forælderen og `ParentGlobalId` i
  barnet. Der foreslås et felt ud fra navnet, men forslaget kan altid ændres.
  Markerede lag gennemsøges i rækkefølge. Er et mållag fra opsætningen ikke
  indlæst lige nu, står det øverst med *(mangler i projektet)* og er markeret,
  så det ikke går tabt når opsætningen gemmes.

Opsætningen skrives til projektet. **Gem projektet bagefter**, ellers går den
tabt. Gemmes den i en skabelon, arver alle afledte projekter den.

### Hvor ligger opsætningen

Som projektegenskab under scope `search_related_features`, nøgle `searchConfigs`,
serialiseret som JSON. Den ender i `<properties>` i `.qgs`-filen inde i
`.qgz`-arkivet.

Skal den sættes op fra konsollen i stedet:

```python
from search_related_features.project_config import configs_from_relations, save_configs
save_configs(configs_from_relations())
```

### Skema

```json
{
  "name": "<navn i dropdownen>",
  "table": "<lag-id eller lagnavn>",
  "table_key": "<feltnavn>",
  "search_fields": ["<feltnavn>", "<feltnavn>"],
  "filter_expression": "\"Status\" < 100",
  "targets": [
    {"layer": "<lag-id>", "key": "<feltnavn>"},
    {"layer": "<lag-id>", "key": "<feltnavn>"}
  ]
}
```

Lag gemmes med id og slås op på id først, dernæst på navn. Et lag kan altså
omdøbes uden at opsætningen går i stykker, og en opsætning kan skrives i hånden
med lagnavne. En tom `search_fields` betyder alle kolonner.

## Designvalg

**Feltnavne frem for relations-id.** Sammenkædningen sker på navngivne felter,
ikke på `QgsRelation.id()`. Feltet i tabellen og feltet i mållaget vælges hver
for sig, så `ParentGlobalId` kan pege på `GlobalID`. Slettes og genoprettes en relation, ændrer id'et
sig, og en gemt opsætning ville pege i tomme luften. Feltparret er også
symmetrisk, så det er ligegyldigt hvilken side der er forælder.

**To opslagsveje.** Ligger lagene på en fjernkilde — `arcgisfeatureserver`,
WFS, en database over netværket — er begge yderpunkter dyre: et fuldt indeks
kræver at hele laget hentes hjem, og et udtryk pr. klik kalder ud til serveren
hver gang. Derfor vælges der efter hvor mange nøgler der skal slås op:

| Antal nøgler | Vej |
|---|---|
| Op til `EXPRESSION_LIMIT` (200) | `IN (...)`-udtryk direkte mod laget, delt op i portioner à 100 |
| Derover, eller når indekset allerede findes | `{nøgle: [feature-id]}`-indeks, bygget én gang pr. lag pr. session |

Et enkelt klik i tabellen koster dermed én lille forespørgsel i stedet for en
hentning af hele laget, mens **Vælg filtrerede rækker** med mange rækker
betaler for indekset og til gengæld får alle efterfølgende opslag gratis.
Svarene på de direkte opslag huskes pr. nøgle, også de tomme, så det samme klik
to gange i træk kun koster én forespørgsel.

Begge veje normaliserer nøglen igen på svaret, da en server kan matche uden
hensyn til store og små bogstaver. Kan udtrykket ikke gennemføres, logges det,
og indekset bygges i stedet. Begge caches ryddes automatisk når laget redigeres,
og når et nyt projekt åbnes.

Tiderne logges i *Vis > Panel > Logbeskeder > search_related_features*, så det kan
ses hvilken vej der blev brugt, og hvad den kostede. Konstanterne står øverst i
`key_index.py`; `EXPRESSION_LIMIT = 0` slår den direkte vej fra.

**Nøgleværdier normaliseres** til trimmede strenge, så tekst/tal-forskelle
mellem de to sider af en relation ikke giver tavse mismatch. Ligger nøglen som
GUID med tuborgparenteser i det ene lag og uden i det andet, skal det håndteres
eksplicit i `normalize_key`.

**Tavs validering.** Opsætninger med manglende tabel eller nøglefelt frasorteres
ved indlæsning og logges i *Vis > Panel > Logbeskeder > search_related_features*.
Et halvt indlæst projekt giver derfor færre valgmuligheder frem for en fejl.

Et enkelt mållag der mangler frasorterer ikke opsætningen: det springes over ved
markering, men bliver stående i opsætningen. Ellers ville et lag, der tilfældigt
ikke kunne indlæses den dag, blive skrevet ud af `.qgz`-filen næste gang
opsætningen blev gemt.
Det dækker også kolonner der kun findes i nogle af tabellerne: en opsætning kan
nævne to stavemåder af det samme feltnavn, og den forkerte droppes pr. tabel.

## Sprog

Brugerfladen er engelsk i kildekoden; dansk leveres som oversættelse. Sproget
vælges i denne rækkefølge:

1. plugin'ets egen indstilling, hvis den er sat
2. `QgsApplication.locale()` — QGIS' effektive sprog
3. systemets sprog

Punkt 2 spørger bevidst QGIS om det sprog der *faktisk* er i brug, i stedet for
at læse `locale/userLocale`. Den nøgle indeholder det sprog der står valgt i
indstillingsdialogen, også når *Tilsidesæt systemlokalitet* er slået fra og
QGIS reelt kører på systemets sprog.

Sprogskift kræver at plugin'et genindlæses — der er bevidst ikke bygget
live-skift, da det ville kræve `retranslateUi()` i hver dialog for en
indstilling der sjældent ændres.

Alle brugervendte tekster er konverteret: 93 strenge i otte kontekster
(`FacetFilter`, `CheckableValueCombo`, `FacetWidget`, `FacetBar`,
`SearchRelatedFeatures`, `ProjectConfig`, `ConfigDialog`, `SearchPanel`).

Logbeskeder oversættes ikke. De er til fejlsøgning og er lettere at søge i, når
de altid står på ét sprog.

### Oversæt

Træk strengene ud af koden og opdater `.ts`-filen:

```
pylupdate5 *.py -ts i18n/search_related_features_da.ts
```

Ret oversættelserne i Qt Linguist, og kompilér til `.qm`:

```
lrelease i18n/search_related_features_da.ts
```

Har din QGIS-installation kun `linguist.exe` og ingen `lrelease.exe`, gør det
ingen forskel: *Filer > Udgiv* i Qt Linguist laver nøjagtig samme `.qm`-fil.
Åbn den med det rigtige miljø:

```powershell
.\build.ps1 -Linguist
```

`build.ps1` kompilerer så ikke selv, men tjekker at der findes en `.qm`, der
ikke er ældre end sin `.ts`, advarer hvis den er forældet, og fejler helt under
`-Release`.

### Når sproget ikke slår igennem

Plugin'et logger sit sprogvalg ved indlæsning i *Vis > Panel > Logbeskeder >
search_related_features*, fx `Language: da loaded from
search_related_features_da.qm`. Mangler `.qm`-filen, står der en advarsel med den
`lrelease`-kommando der skal køres.

Hele beslutningen kan slås op i konsollen:

```python
from search_related_features.translation import report
for key, value in report().items():
    print(key, "=", value)
```

`.qm`-filerne **skal med i zip'en** — uden dem falder alt tilbage til engelsk,
uden nogen fejlmeddelelse. Et nyt sprog kræver kun en ny `.ts`-fil og en linje
i `AVAILABLE` i `translation.py`.

### For udvikleren

Brugervendte strenge skrives på engelsk og pakkes ind:

- inde i en `QObject`: `self.tr("Add")` — klassenavnet bliver konteksten
- uden for en `QObject`: `_tr("(empty)")`, som sætter konteksten eksplicit

To fælder er værd at kende. **Strenge på modulniveau** evalueres ved import,
altså før oversætteren er installeret — derfor er `EMPTY_LABEL` og `ALL_LABEL`
lavet om til funktionerne `empty_label()` og `all_label()`. Og **pladsholdere
skal nummereres**, `"{0} selected"` og ikke `"{} selected"`, da ordstillingen
er forskellig fra sprog til sprog, og oversætteren skal kunne bytte om på dem.

Brugerens egne data — feltnavne, aliaser, værdilisternes tekster og `name` i
opsætningen — oversættes ikke.

## Filer

```
search_related_features/
├── __init__.py                 classFactory
├── metadata.txt
├── search_related_features.py     hovedklasse: værktøjslinje, menu, projekthooks
├── search_panel.py             dokpanelet med søgning, filtre og markering
├── facet_filter.py             kolonnefiltre med kaskaderende værdilister
├── value_format.py             oversætter gemte koder til viste tekster
├── config_dialog.py            opsætningsdialog
├── project_config.py           læs/skriv opsætning i projektet, validering
├── key_index.py                nøgleindeks med cache
├── translation.py              sprogvalg og indlæsning af oversættelser
├── i18n/                       .ts-kilder og kompilerede .qm-filer
└── images/
```

## Kendte begrænsninger

- Kan datakilden ikke oversætte `IN (...)` til et server-kald, evaluerer QGIS
  udtrykket lokalt og henter laget igennem alligevel. Så er den direkte vej
  ikke hurtigere end indekset, men til gengæld heller ikke langsommere — det
  kan ses på tiderne i logbeskederne.
- Tabellen indlæses helt i hukommelsen og filtreres lokalt. Fint op til nogle
  titusinde rækker. Derover bør `_populate` laves om til et
  `setFilterExpression`-kald pr. søgning.
- Kolonnefiltrenes kaskade gennemløber alle rækker pr. aktivt filter. Med mange
  rækker og mange samtidige filtre kan opdateringen blive mærkbar; så skal
  værdioptællingen caches pr. kolonne i stedet.
- Kolonnefiltre kan endnu ikke gemmes i opsætningen som et forvalg. Vil man have
  et fast forfilter, bruges `filter_expression` i opsætningsdialogen.
- **Følg kortvalg** kolliderer med markeringslogikken i SelectByRelationship,
  hvis begge plugins er aktive på de samme relationer.
- Qt6 er ikke understøttet (`supportsQt6=False`). De ikke-omfangsbestemte
  Qt-enums, fx `Qt.UserRole` og `QDialogButtonBox.Save`, skal skrives om til
  `Qt.ItemDataRole.UserRole`-formen først.

## Udvikling

Ved genindlæsning med Plugin Reloader skal `unload()` rive alt ned med det samme.
`deleteLater()` er udskudt til næste gennemløb af hændelsesløkken, og reloaderen
tjekker straks efter unload — derfor bruges `sip.delete()` via `delete_now()`.
Efterlades widgets, kommer advarslen:

```
WARNING: removing duplicated widget(s) not cleaned up by the plugin
during unload: SearchRelatedFeaturesToolbar, SearchRelatedFeaturesPanel
```

Tjek i konsollen at der ikke er noget tilbage efter unload:

```python
from qgis.PyQt.QtWidgets import QToolBar, QDockWidget
win = iface.mainWindow()
print([w.objectName() for w in win.findChildren(QToolBar) + win.findChildren(QDockWidget)
       if w.objectName().startswith("SearchRelatedFeatures")])
```

## Licens

GNU General Public License v2 eller senere.
