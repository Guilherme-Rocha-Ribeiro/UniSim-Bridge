# UnisimConnector.py

`UnisimConnector.py` is the **library**. It connects Python to UniSim Design through COM, reads the properties of the objects you selected at every time step, and stores them in an SQLite database. You normally do not edit it. You import one class from it:

```python
from UnisimConnector import SimulationConnector
```

!!! info "Requirements"
    - Windows with UniSim Design installed (the library uses `win32com`).
    - Python packages: `pywin32` and `pandas`. `sqlite3` is part of the standard library.
    - Type hints such as `list[str]` require Python 3.9 or newer.

!!! note "Authors"
    Guilherme Ribeiro, Daniel Diniz, Raony Fontes.

---

## File layout

The file is a single module with three layers:

```
UnisimConnector.py
│
├── binary_search()            utility
│
├── Operation                  base class (shared logic)
│   ├── MaterialStreams        + StreamComponents, MaterialStreams.Phase
│   ├── Valves
│   ├── Pumps
│   ├── Compressors
│   ├── Controllers
│   ├── HeatExchangers
│   ├── Flashtanks
│   ├── Heaters
│   ├── Coolers
│   └── Pipesegs
│
├── Spreadsheets               separate class (not an Operation subclass)
│
└── SimulationConnector        orchestrator, the public entry point
```

| Component | Responsibility |
|---|---|
| `binary_search` | Fast name lookup in a sorted list of strings |
| `Operation` | Validates names, caches COM property objects, creates tables, inserts rows, exports CSV |
| `MaterialStreams` | Bulk, component-level and phase-level data of streams |
| `StreamComponents` | Holder of component data (mass/molar flows and fractions) |
| `Spreadsheets` | Reads individual cells of spreadsheet operations |
| Equipment classes | Only declare the UniSim type name and the default properties |
| `SimulationConnector` | Opens UniSim, owns all handlers, runs steps, finishes the run |

---

## Operation

`Operation` is the base class of every equipment handler. It contains all the shared logic (name validation, property cache, table creation, row insertion, CSV export), so a subclass only declares **what** to read. The concepts (what an operation is in UniSim, which types exist and which properties they expose) are explained in [Operations](../reference/operations-reference.md). This section describes the code.

### Class structure

```
Operation                          shared logic
│
├── Valves           'valveop'
├── Pumps            'pumpop'
├── Compressors      'compressor'
├── Controllers      'fbcontrolop'
├── HeatExchangers   'heatexop'
├── Flashtanks       'flashtank'
├── Heaters          'heaterop'
├── Coolers          'coolerop'
├── Pipesegs         'pipeseg'          overrides _update_data
└── MaterialStreams  'materialstream'   overrides _build_data, _update_data, _save_to_csv
```

`Spreadsheets` does not inherit from `Operation` because it reads cells, not named properties, but it implements the same four methods, so `SimulationConnector` treats it like the others (see [Interface used by the connector](#interface-used-by-the-connector)).

A subclass defines only:

| Member | Meaning |
|---|---|
| `_operation_title`  | UniSim `TypeName` of the objects. It is also used as the **table name**. |
| `properties` | `{property: unit}` recorded by default. |

### Constructor and attributes

```python
Operation(db_conn: sqlite3.Connection, db_tag: str, cursor: sqlite3.Cursor)
```

The connection, the cursor and the tag are **shared** with the `SimulationConnector` and with all other handlers.

| Attribute | Type | Content |
|---|---|---|
| `_operation_title` | `str` | UniSim `TypeName`. Overridden by each subclass. |
| `_names` | `list[str]` | Names requested in the setup. Exposed as `names`. |
| `objects` | `dict[str, CDispatch]` | Validated COM objects, keyed by name. |
| `_properties` | `dict[str, str]` | `{property: unit}`. Exposed as `properties`. |
| `comObjs_properties` | `dict` | Cache `{name: {property: (COM property object, unit)}}`. |
| `data` | `dict` | Values read in the most recent step, `{name: {'time': t, property: value}}`. |
| `db_conn`, `cursor`, `db_tag` | | Database connection, cursor and run tag. |
| `df` | `DataFrame` | Created by `_save_to_csv()` after an export. Does not exist before. |

### Public interface

| Member | Behavior |
|---|---|
| `names` | Getter returns the list. The setter **extends** the list (`handler.names = [...]` appends). |
| `properties` | Getter returns the dictionary. The setter **merges** (`dict.update`), so defaults are kept and an existing key gets its unit replaced. |
| `handler['VLV-100']` | Returns the COM object of a validated name. Raises `KeyError` if the name is not in `objects`. |
| `get_table_name()` | Returns `_operation_title`, except for streams (`materialstream_properties`). |

The object returned by `handler['name']` is the live COM object, so it is also how you change values during a run:

```python
Simulation.valves['VLV-100'].ActuatorPosition.SetValue(100, '%')
```

### Interface used by the connector

`SimulationConnector` drives every handler through the same four methods:

```
build_objects()   →  handler._build_object(handler.names, operations, subflowsheet_operations)
                  →  handler._build_data(0.0)
update()          →  handler._update_data(time=t)
finish()          →  handler._save_to_csv(output_folder)
```

The underscore marks these as internal: you rarely call them yourself. Any new class that implements these four methods can be added to the connector.

### Life cycle

```
easy_setup()        names stored in  .names
     │
build_objects()     _build_object()                 validate names → .objects
     │              _build_data(0.0)
     │                ├─ build_properties_cache()   keep COM property objects
     │                ├─ create_operation_table()   CREATE TABLE / ALTER TABLE
     │                └─ _update_data(0.0)          first row (t = 0)
     │
update()            _update_data(t)  ──► _insert_row_to_db()
     │
finish()            _save_to_csv()   (optional)
```

### Methods

#### `_build_object()`

```python
_build_object(name_list, unisim_operation_object, unisim_subflow_op_object) -> None
```

Validates the requested names against the case and fills `objects`.

1. Builds a sorted list of the upper-cased names of the main flowsheet and looks each requested name up with `binary_search` (so the check is case-insensitive).
2. If found, it checks that the object's `TypeName` matches `_operation_title` and stores the COM object. A mismatch prints `Wrong type for X: expected A, got B`.
3. If not found, it tries each subflowsheet collection in order. If every attempt fails (or there are no subflowsheets), it prints `'X' not found in <type> list.`
4. Names that failed are **removed from `name_list` in place**. Because the connector passes `handler.names`, afterwards `names` contains only valid names.

#### `build_properties_cache()`

For each valid object and each property, it fetches the COM property object once (`getattr(obj, prop_name)`) and stores it with its unit in `comObjs_properties`. Each later step then only calls `GetValue(unit)`. The authors report a 150% speed-up in data collection from this cache, because every attribute lookup crosses the Python/COM boundary.

!!! warning "A property that does not exist on the object"
    If `getattr` fails, the property is skipped silently and is absent from the cache. The step then has no value for it, and `_insert_row_to_db()` raises a `KeyError` for that property. In practice, a misspelled or unsupported property name fails during `build_objects()`. Check the exact name in the case before adding it (see [COM Navigation](../reference/com-navigation.md)).

#### `_build_data()`

```python
_build_data(time: float) -> None
```

Initializes the recording: builds the property cache, creates (or evolves) the table, and records the first row.

#### `_update_data()`

```python
_update_data(time: float) -> None
```

Reads every cached property with `GetValue(unit)` and stores the result in `data`. A value that cannot be read is stored as `None` (`NULL` in the database) and the run continues. After each object, it calls `_insert_row_to_db(self.data)`.

!!! note "Repeated writes"
    The insert is called inside the loop over objects and receives the whole `data` dictionary, so earlier objects are written again for each new object. The upsert makes this harmless for the data, but it means roughly n(n+1)/2 row writes per step for n objects, each followed by a commit.

#### `_insert_row_to_db()`

```python
_insert_row_to_db(data: dict) -> None
```

Writes one row per object with the columns `name`, `time`, `simulation_tag`, `date` and one column per property.

- `time` is formatted with four decimals (`:.4f`) and `date` is the current day as `dd-mm-yyyy`.
- It is an **upsert**: a repeated `(name, time, simulation_tag)` overwrites the property values.
- It commits at the end.

!!! danger "A handler with objects but no properties fails"
    The upsert clause is built from the property names. With an empty `properties` dictionary (the default of `Pumps`), the generated SQL is incomplete and `build_objects()` raises `sqlite3.OperationalError: incomplete input`. If you list pumps, add at least one property first (for example `Simulation.pumps.properties = {'Energy': 'kW'}`). An empty `PUMPS` list is fine.

#### `create_operation_table()`

Creates the table if needed, with `name TEXT`, `time REAL`, `simulation_tag TEXT`, `date TEXT` and one `REAL` column per property, with primary key `(name, time, simulation_tag)`. It then compares the table with `properties` and runs `ALTER TABLE ... ADD COLUMN` for each missing property, printing `new column added to <table> <property>`. This is what allows a database from an earlier run to accept new properties.

#### `_save_to_csv()`

```python
_save_to_csv(output_folder: str) -> None
```

Selects all columns except `simulation_tag` for the current tag, builds a DataFrame indexed by `name`, keeps it in `self.df` and writes `<output_folder><TAG>_<table>_data.csv`. Nothing is written when there are no rows. The path is built by concatenation, so the folder must end with a separator.

### Overridden behavior

**`Pipesegs`** replaces `_update_data()`. It reads `GetValue` and, if the property is a vector (segment properties such as `SegmentLength`), falls back to `GetValues` and stores the **sum** of the segments. A sum makes sense for lengths and elevation changes, not for diameters.

!!! warning "Verify pipes before relying on them"
    `Pipesegs._update_data()` stores one-row DataFrames in `data`, while `_insert_row_to_db()` formats `data_['time']` with `:.4f`, which pandas does not support for a Series (`TypeError`). From reading the code, listing a pipe is likely to fail at `build_objects()`. Neither example script lists pipes (`PIPES = []`), so this path is untested. Check it on a case with pipes before using it.

**`MaterialStreams`** overrides `_build_data()`, `_update_data()` and `_save_to_csv()` to add component and phase data. See [MaterialStreams](#materialstreams).

**`Spreadsheets`** implements its own versions of the four methods, with a `{spreadsheet: [cells]}` dictionary in place of names. See [Spreadsheets](#spreadsheets).

---

## Equipment classes

Each class is a few lines: it sets `_operation_title` (the UniSim `TypeName`) and the default `properties` (`{name: unit}`). Everything else is inherited from `Operation`.

| Attribute of `SimulationConnector` | Class | UniSim `TypeName` | Default properties | Table |
|---|---|---|---|---|
| `valves` | `Valves` | `valveop` | `ActuatorPosition`, `PressureDrop`, `FeedTemperature`, `FeedPressure`, `MolarFlow`, `MassFlow` | `valveop` |
| `pumps` | `Pumps` | `pumpop` | *(none)* | `pumpop` |
| `compressors` | `Compressors` | `compressor` | `MassFlow`, `FeedTemperature`, `FeedPressure`, `CompressorSpeed`, `CompAdiabaticEff`, `AdiabaticHead`, `Energy`, `PressureIncrease` | `compressor` |
| `controllers` | `Controllers` | `fbcontrolop` | `SP`, `PV`, `OP`, `RampDuration` | `fbcontrolop` |
| `heat_exchangers` | `HeatExchangers` | `heatexop` | `Duty` | `heatexop` |
| `flashtanks` | `Flashtanks` | `flashtank` | `VesselPressure`, `VesselTemperature` | `flashtank` |
| `heaters` | `Heaters` | `heaterop` | `MassFlow`, `FeedTemperature`, `FeedPressure`, `ProductTemperature` | `heaterop` |
| `coolers` | `Coolers` | `coolerop` | `MassFlow`, `FeedTemperature`, `FeedPressure`, `ProductTemperature` | `coolerop` |
| `pipes` | `Pipesegs` | `pipeseg` | `PressureDrop` | `pipeseg` |
| `material_streams` | `MaterialStreams` | `materialstream` | see [MaterialStreams](#materialstreams) | `materialstream_properties` |
| `spreadsheets` | `Spreadsheets` | `spreadsheetop` | cells chosen in the setup | `spreadsheet_<NAME>` |

!!! warning "Pumps have no default properties"
    `Pumps` starts with an empty property list. Listing a pump without adding at least one property makes `build_objects()` fail (see [`_insert_row_to_db()`](#_insert_row_to_db)). Add what you need before `build_objects()`:

    ```python
    Simulation.pumps.properties = {'Energy': 'kW'}
    ```

The complete reference of default properties and units is in [Operations](../reference/operations-reference.md).

---

## MaterialStreams

`MaterialStreams` records the state of the material streams of the flowsheet. It is the most detailed handler of the library, because a stream carries information at three levels: the stream as a whole, its components, and each of its phases. It is available as `Simulation.material_streams`.

Unlike the equipment classes, streams are searched in `Flowsheet.Streams` (and in the `Streams` collection of each subflowsheet), not in `Flowsheet.Operations`.

### Three levels of data

| Level | Dictionary | Default content | Tables |
|---|---|---|---|
| Bulk | `properties` | `Pressure`, `StdGasFlow`, `MassFlow`, `MolarFlow`, `StdLiqVolFlow`, `Temperature`, `MassDensity`, `VapourFraction`, `ActualGasFlow`, `ActualLiqFlow`, `ActualVolumeFlow` | `materialstream_properties` |
| Components | `components_properties` | `ComponentMassFlow`, `ComponentMolarFlow`, `ComponentMolarFraction`, `ComponentMassFraction` | `materialstream_components` |
| Phases | `phase_properties` | `MassFlow`, `MolarFlow`, `MassDensity`, `ActualVolumeFlow`, `Viscosity`, `PhaseFraction` | `<phase>_properties` and `<phase>_components` |

The three phases are `VapourPhase`, `LightLiquidPhase` and `HeavyLiquidPhase`, so the phase tables are `vapourphase_properties`, `vapourphase_components`, `lightliquidphase_properties`, `lightliquidphase_components`, `heavyliquidphase_properties` and `heavyliquidphase_components`.

Phase data is only collected for the streams listed in `material_streams_phase` (stored in `collected_phases`). It is the heaviest part of the collection, so request it only where you need it.

### How each level is stored

**Bulk properties** are scalars, handled exactly like any other operation: one row per stream and time, with one column per property.

**Components** are vectors with one value per chemical component. They are read with `GetValues(unit)` and stored in `materialstream_components` with **one column per component** and one row per property:

| stream_name | time | simulation_tag | property_type | Methane | Ethane | ... |
|---|---|---|---|---|---|---|
| `feed_sep` | 0.033 | `teste` | `ComponentMassFlow` | 120.4 | 35.1 | ... |
| `feed_sep` | 0.033 | `teste` | `ComponentMolarFraction` | 0.71 | 0.19 | ... |

**Phases** follow the same idea. The phase property tables have one column per property (`stream_name`, `time`, `simulation_tag`, `MassFlow`, ...). The phase component tables use `property_type` with the values `MassFractions` and `MolarFractions`, and one column per component.

!!! note "Component names"
    The component columns come from the fluid package of the **first valid stream**. All recorded streams are assumed to share the same fluid package.

### Customizing the properties

Each dictionary accepts additions in the same way as the equipment handlers: assigning **merges** with the existing entries.

```python
Simulation.material_streams.properties = {'Temperature': 'K'}            # bulk
Simulation.material_streams.phase_properties = {'Temperature': 'K'}      # per phase
Simulation.material_streams.components_properties = {'ComponentMolarFraction': ''}
```

Assigning a key that already exists replaces its unit.

!!! warning "Set properties before `build_objects()`"
    The COM property objects are cached and the tables are created inside `build_objects()`. Changes made afterwards are ignored.

!!! warning "Units are not stored in the database"
    The tables have no unit column. If you change a unit and reuse the same database, values of different runs will be mixed with no marker. Each run writes the units it used to `_simulation_properties.txt`, and a new tag per unit configuration keeps runs distinguishable.

### Reading the data

```python
import sqlite3, pandas as pd
conn = sqlite3.connect('db_name1.db')

# Bulk
bulk = pd.read_sql(
    "SELECT time, Temperature, MassFlow FROM materialstream_properties "
    "WHERE name = 'feed_sep' AND simulation_tag = 'teste' ORDER BY time", conn)

# Components of the stream
comps = pd.read_sql(
    "SELECT * FROM materialstream_components "
    "WHERE stream_name = 'feed_sep' AND property_type = 'ComponentMolarFraction' "
    "AND simulation_tag = 'teste' ORDER BY time", conn)

# One phase
vapour = pd.read_sql(
    "SELECT time, MassFlow, Viscosity FROM vapourphase_properties "
    "WHERE stream_name = 'pump_1_in' AND simulation_tag = 'teste' ORDER BY time", conn)
```

Note that the bulk table identifies the stream in the `name` column, while the components and phase tables use `stream_name`. See [Database Tables](#database).

### Behavior to be aware of

- A property that cannot be read (for example, the viscosity of a phase that does not exist in that stream) is stored as `NULL`. The run continues.
- At least **one valid stream** is required. The library reads the component list from the first stream in `objects`. If every name is rejected, `build_objects()` fails at this point.
- The bulk and phase **property** tables are *upserted* (a repeated `(stream, time, tag)` overwrites the row). The **component** tables use `INSERT OR IGNORE`, so a repeated key keeps the old values. When you rerun with the same database, use a new tag.

## Spreadsheets

`Spreadsheets` is not an `Operation` subclass because it reads **cells**, not named properties. The setup is `{spreadsheet: [cells]}`. At each step it reads `Cell(cell).CellValue` and stores one row per cell in a table named `spreadsheet_<NAME>` (name in upper case) with the columns `cell`, `time`, `simulation_tag`, `date`, `value`.

---

## SimulationConnector

The only class most users need.

### Creating the connector

```python
SimulationConnector(file_path_unisim, OUTPUT_FOLDER, db_tag,
                    db_name='Simulation.db',
                    continue_simulation=True, case_visible=True)
```

| Argument | Description |
|---|---|
| `file_path_unisim` | Path of the `.usc` file |
| `OUTPUT_FOLDER` | Folder for text and CSV outputs (created if missing) |
| `db_tag` | Label of this run, stored in every row |
| `db_name` | SQLite file |
| `continue_simulation` | `False` resets the integrator, `True` keeps the saved state |
| `case_visible` | Show or hide the UniSim window |

The constructor, in order:

1. Opens the SQLite connection and sets `synchronous = NORMAL`, `journal_mode = WAL` and a ~256 MB cache, which favors fast writes during long runs.
2. Creates `OUTPUT_FOLDER` if needed.
3. Starts UniSim (`UnisimDesign.Application`), opens the case and sets its visibility.
4. Stores the UniSim process id in `process_id` and gets the solver integrator (`Solver.Integrator`) as `integrador`, with `Mode = 0`. The integrator is reset when `continue_simulation` is `False`.
5. Creates one handler per operation type (`material_streams`, `valves`, `pumps`, `pipes`, `heat_exchangers`, `compressors`, `controllers`, `flashtanks`, `coolers`, `heaters`, `spreadsheets`).

!!! note "`operations` list"
    `Simulation.operations` holds the **equipment** handlers only. `material_streams` and `spreadsheets` are handled separately by the library because their data structures differ.

### Main methods

| Method | When | What it does |
|---|---|---|
| [`easy_setup(**kwargs)`](#easy_setup) | After creating | Stores the names to record |
| [`build_objects(subFlowsheet=[])`](#build_objects) | After setup | Validates names, creates tables, records t = 0 |
| [`update(sample_time, time_unit, id)`](#update) | Every step | Advances the solver and records one row per object |
| [`finish(quit_unisim, save_simulation, export_csv)`](#finish) | End | Writes summary files, closes database and UniSim |

## Finishing a run

A run ends with `Simulation.finish(...)`. It closes the loop that started with `SimulationConnector(...)`: it writes the documentation files of the run, optionally exports the data, and releases the database and UniSim.

### Sequence

1. **Summary file**: writes `_simulation_summary.txt` with the case file name and, for each group, the objects that were actually found. This is the quickest way to confirm which names survived the validation of `build_objects()`.
2. **Units file**: writes `_simulation_properties.txt` with every tracked property and its unit, per operation type (and per level for material streams).
3. **CSV export** (only if `export_csv=True`): writes one file per table, filtered by the current tag, as `<TAG>_<table>_data.csv`.
4. **Database**: closes the SQLite connection.
5. **UniSim** (only if `quit_unisim=True`): closes the case and quits the application.

Errors in steps 1 to 3 are printed with a traceback but do not prevent the following steps. The database is always closed.

### Output files

| File | Always written | Content |
|---|---|---|
| `_simulation_summary.txt` | yes | Case name and objects found per group |
| `_simulation_properties.txt` | yes | Tracked properties and units |
| `<TAG>_<table>_data.csv` | only with `export_csv=True` | Table content for this tag (`simulation_tag` excluded) |
| `*.db` | created at start | All recorded data, always available even without CSV export |

### Closing behavior

| Situation | `quit_unisim` | `save_simulation` | Result |
|---|---|---|---|
| Normal end | `True` | `True` | Case saved, UniSim closed |
| Normal end | `True` | `False` | Case closed without saving, UniSim closed |
| Normal end, keep it open | `False` | any | UniSim stays open (useful for debugging) |
| Run aborted by an error | `False` (recommended) | ignored | UniSim stays open so you can inspect the state |

When `save_simulation` is `None` (the default), the library saves only if the run was created with `continue_simulation=True`. This makes a *continue* workflow save its state automatically, while a first run does not overwrite the original case.

!!! warning "The `_simulation_abort` flag"
    The connector has an internal flag, `_simulation_abort`, initialized to `False`. When it is `True` and `quit_unisim=True`, `finish()` does not close the case normally and instead terminates UniSim with `taskkill /f /im unisimdesign.exe`, which closes **every** UniSim process on the machine. The library itself never sets this flag, so the branch is only reached if your own code sets it. For ordinary errors, pass `quit_unisim=False` and close UniSim yourself.

### Recommended pattern

```python
aborted = False
for step in range(N_SIM_STEPS):
    try:
        Simulation.update(TIME_STEP_SIZE, TIME_STEP_UNIT)
    except Exception:
        traceback.print_exc()
        aborted = True
        break

Simulation.finish(
    quit_unisim=not aborted,
    save_simulation=SAVE_SIMULATION,
    export_csv=EXPORT_CSV,
)
```

!!! warning "Trailing separator in `OUTPUT_FOLDER`"
    CSV paths are built by concatenating `OUTPUT_FOLDER` and the file name. End the folder path with a separator (`os.path.join(folder, '')`), as explained in [main.py](main.md#2-run-configuration).

## Functions

Reference of the public methods of `SimulationConnector`. The usual order of a run is `easy_setup()` → `build_objects()` → `update()` (repeated) → `finish()`.

### Easy_Setup()

```python
easy_setup(**kwargs) -> None
```

Declares **what to record**. It receives one list of names per operation type, validates them and stores them in the handlers. It does not talk to UniSim: nothing is checked against the case until [`build_objects()`](#build_objects).

#### Arguments

All twelve keyword arguments are required, even when empty.

| Argument | Type | Handler that receives it |
|---|---|---|
| `pumps` | `list[str]` | `pumps` |
| `valves` | `list[str]` | `valves` |
| `flashtanks` | `list[str]` | `flashtanks` |
| `compressors` | `list[str]` | `compressors` |
| `controllers` | `list[str]` | `controllers` |
| `heat_exchangers` | `list[str]` | `heat_exchangers` |
| `material_streams` | `list[str]` | `material_streams` |
| `material_streams_phase` | `list[str]` | `material_streams` (subset with phase data) |
| `heaters` | `list[str]` | `heaters` |
| `coolers` | `list[str]` | `coolers` |
| `pipes` | `list[str]` | `pipes` |
| `spreadsheets` | `dict[str, list[str]]` | `spreadsheets` (`{name: [cells]}`) |

#### What it does

1. **Validates the types**. A `list` of strings is expected for every argument except `spreadsheets`, which must be a dictionary of lists. Other types (a tuple or a set, for example) or non-string items raise `TypeError`.
2. **Removes duplicates** by converting each list to a set. The original order is lost.
3. **Merges the stream lists**. `material_streams` receives the union of `material_streams` and `material_streams_phase`, and `collected_phases` receives `material_streams_phase`. A stream that needs phase data therefore does not have to be listed twice.
4. **Stores the names** in each handler (`Simulation.valves.names`, ...) and the cell map in `Simulation.spreadsheets.cells`.

#### Example

```python
Simulation.easy_setup(
    pumps=[],
    valves=['VLV-100', 'VLV-101'],
    flashtanks=['V-100'],
    compressors=['pump_1', 'pump_2'],
    controllers=['LIC-100'],
    heat_exchangers=['E-100'],
    material_streams=['feed_sep', 'gas_sep'],
    material_streams_phase=['pump_1_in'],      # also added to material_streams
    heaters=[],
    coolers=[],
    pipes=[],
    spreadsheets={'RGO': ['B24', 'F24']},
)
```

#### Notes

- **Missing argument:** raises `KeyError` (for example `KeyError: 'pumps'`). Pass an empty list instead.
- **Call it once.** Each call *appends* to the handlers' name lists, so a second call duplicates names. The spreadsheet map and `collected_phases` are replaced instead.
- **Names in the wrong place** are not detected here. A valve listed under `pumps` is only reported by `build_objects()`.
- The usual source of these lists is the [setup file](setup.md).

### Build_Objects()

```python
build_objects(subFlowsheet=[]) -> None
```

Connects the names declared in `easy_setup()` to the real objects in the case. For each name it searches the main flowsheet and then the subflowsheets in `subFlowsheet`, checks the UniSim type, and discards names that are missing or of the wrong type (with a printed message). Then it builds the property caches, creates the tables and records the **t = 0** row.

| Argument | Description |
|---|---|
| `subFlowsheet` | Names of subflowsheets to search (e.g. `['ColumnSubFlowsheet']`). Defaults to none. |

Add custom properties **before** calling it. See [main.py](main.md#4-adding-properties-that-are-not-recorded-by-default).

### Update()

```python
update(sample_time=None, time_unit=None, id=None) -> None
```

Advances the solver and records one row per tracked object.

| Call | Behavior |
|---|---|
| `update(1.0, 'hr')` | Runs the solver for the interval (`RunFor`), then records at the new solver time |
| `update(id=10)` | Records at the given identifier without advancing the solver |

!!! warning "Numeric time or id"
    The time column is written with a fixed numeric format (`:.4f`), so `id` must be a **number**. Calling `update()` with no arguments is not supported in the current version for the same reason: the time would be an empty string.

### Finish()

```python
finish(quit_unisim=True, save_simulation=None, export_csv=False) -> None
```

Writes the run files, optionally exports CSV, closes the database and (optionally) UniSim. The full behavior, including the closing scenarios, is described in [Finishing a run](#finishing-a-run).

| Argument | Description |
|---|---|
| `quit_unisim` | Close the case and quit UniSim when `True` |
| `save_simulation` | Save the case when closing. `None` follows `continue_simulation` |
| `export_csv` | Export every tracked table to CSV |

### Discovery helpers

Use them to list the real names and types in a case. They query UniSim and do not depend on the setup.

| Method | Returns |
|---|---|
| `get_material_streams()` | Sorted list of stream names |
| `get_valves()`, `get_pumps()`, `get_compressors()`, `get_controllers()`, `get_heatexchangers()`, `get_flashtanks()`, `get_spreadsheets()` | Names of that operation type |
| `get_subflowsheets()` | `[(Name, TaggedName), ...]` |
| `get_all_operations()` | `{TypeName: [names]}` for every operation in the flowsheet |

There are no dedicated helpers for pipes, heaters and coolers. Use `get_all_operations()` for those.

### Custom database methods

The connector also exposes generic helpers to store your own data (experiment notes, derived metrics) in the same database:

| Method | Purpose |
|---|---|
| `create_table(table_name, columns, primary_keys=None)` | Create a table from column definitions |
| `add_columns(table_name, columns)` | Add columns to an existing table |
| `insert_row(table_name, data, conflict_columns=None, update_columns=None)` | Insert, with optional upsert |
| `update_row(table_name, data, condition_columns)` | Update rows matching the condition columns |
| `query_table(table_name, conditions=None, order_by=None, limit=None)` | Select rows, returns a list |
| `get_table_info(table_name)` | Column information of a table |

---

## Database

One SQLite file holds every run. Rows are separated by the `simulation_tag` column and **upserted** on `(name, time, simulation_tag)`, so recording the same time twice for the same tag overwrites instead of duplicating.

Common columns of the equipment tables:

| Column | Content |
|---|---|
| `name` | Object name |
| `time` | Solver time (in the unit used in `update`) |
| `simulation_tag` | Run label |
| `date` | Run date (`dd-mm-yyyy`) |
| *one column per property* | Recorded value (`REAL`) |

Schema changes are automatic: when you add a property, the library adds the missing column to existing tables.

Example query with pandas:

```python
import sqlite3, pandas as pd

conn = sqlite3.connect('db_name1.db')
df = pd.read_sql(
    "SELECT time, ActuatorPosition, MassFlow "
    "FROM valveop WHERE name = 'VLV-100' AND simulation_tag = 'teste' ORDER BY time",
    conn,
)
```

---

## Extending the library

To support a new UniSim operation type, add a class in the same style as the existing ones:

```python
class MyOperations(Operation):
    def __init__(self, db_conn, db_tag, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = '<TypeName>'   # UniSim TypeName of the object
        self.properties = dict(
            # PropertyName='unit',
        )
```

Then, inside `SimulationConnector`:

1. Create the handler in `__init__` (`self.my_operations = MyOperations(...)`) and add it to `self.operations`.
2. Read its names in `easy_setup`.
3. Add a line for it in the summary written by `finish()`.

Use `get_all_operations()` to discover the `TypeName` of the new object.

---

## Known limitations

- **Windows only**, with UniSim installed (COM).
- `easy_setup()` requires every argument, even when empty.
- `build_objects(subFlowsheet=[])` uses a mutable default argument. This is harmless today, because the list is never modified, but passing the list explicitly is safer.
- Names are de-duplicated through sets, so the original order is lost.
- The module is a single file. This is deliberate for the current version and is expected to be split into a package in a later one.
- A pump listed without any property raises an SQL error in `build_objects()`.
- Pipe segments (`Pipesegs`) are likely to fail when listed. The code path is not exercised by the example scripts.
- `Operation._update_data()` rewrites earlier objects for each new object in the same step, which scales quadratically with the number of objects of a type.