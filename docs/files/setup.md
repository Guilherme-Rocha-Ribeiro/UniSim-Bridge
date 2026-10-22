# setup.py

`setup.py` is the configuration file of a simulation project. It contains only constants that answer one question: which objects of the UniSim case should be recorded?

The user must define the names of the Material Streams, Subflowsheets, Spreadsheets, and Equipment they want to monitor, following the rules below


## Rules
### Names must match the `.usc` file

The names you pass in must match the names as they appear in your `.usc`file.

**Case does not matter** These are all treated as the same name:.  
```python
VALVES = ["VLV-100"]
VALVES = ["vlv-100"]
VALVES = ["vLV-100"]
```
UniSim-Bridge's existence check ignores case, so either form will find the object.

However **special characters, accents, other non-ASCII characters and spacing** do matter in practice. Even though the check is case-insensitive, copying names exactly as they appear in the `.usc` file avoids erros. 

For example:

```python
# Space vs. hyphen vs. underscore — three different names:
MATERIALSTREAMS = ['liq sep'] 
MATERIALSTREAMS = ['liq-sep']
MATERIALSTREAMS = ['liq_sep'] 

# Accents and spacing — three more different names:
MATERIALSTREAMS = ['poço de produção'] 
MATERIALSTREAMS = ['poco de producao'] 
MATERIALSTREAMS = ['poço_de_produção'] 

```

!!! warning "These may look like variations of the same name, but to UniSim they are different objects:"

    - 'liq sep', 'liq-sep', and 'liq_sep' are three separate objects. The space, hyphen, and underscore are not interchangeable.

    - 'poço de produção', 'poco de producao', and 'poço_de_produção' are likewise three separate names. Accents are significant (ç ≠ c, ã ≠ a), and a space is not the same as an underscore.


!!! info "Tip"
    To guarantee that a name is correct, use the [utility functions](../reference/utilities-functions.md) to list the names in the open case, or copy the name directly from the `.usc` file.

### Almost every variable is a list of strings
With the exception of [spreadsheets](#spreadsheets), every variable in `setup.py` follows this shape:

```python
equipment_type: list[str] = ['object_name']
```

In other words: 
- The value is always a list, even when it holds a single object or none at all, becoming an empty list.
- Each item is a string matching a name in the `.usc` file ([see the previous rule](#names-must-match-the-usc-file))

The correct way to pass the values are as follows

```python
# Correct — always a list of strings
valves: list[str] = ['VLV-100', 'VLV-101']
flashtanks: list[str] = ['V-100']
material_streams: list[str] = ['feed_sep', 'liq sep', '1']

# Also correct — an empty list when there is nothing to monitor
pumps: list[str] = []
heaters: list[str] = []



# When an object lives inside a subflowsheet, list the subflowsheet in --SUBFLOWSHEETS--. 
# The library searches the main flowsheet first and then each subflowsheet.
SUBFLOWSHEETS = ['TPL1, TPL2']
```

!!! failure "Incorrect passage"
```python
    # Wrong — a bare string, not a list
    valves = 'VLV-100'

    # Wrong — a tuple, not a list
    valves = ('VLV-100',)

    # Wrong — None instead of an empty list
    pumps = None
```


### Spreadsheets

The dictionary maps the spreadsheet **name** to the **cells** to read:

```python
SPREADSHEETS = {'RGO': ['B24', 'F24']}   # reads cells B24 and F24 of spreadsheet "RGO"
```

---

## Expected Variables in the file

| Variable | Type | Content |
|---|---|---|
| `path_unisim` | `str` | Full path of the `.usc` case file |
| `SUBFLOWSHEETS` | `list[str]` | Subflowsheets to search for objects (empty list if none) |
| `MATERIAL_STREAMS` | `list[str]` | Material streams to record |
| `MATERIAL_STREAMS_PHASE` | `list[str]` | Streams for which **phase-level** data is also recorded |
| `FLASHTANKS` | `list[str]` | Flash tanks |
| `CONTROLLERS` | `list[str]` | Feedback controllers |
| `VALVES` | `list[str]` | Valves |
| `HEAT_EXCHANGERS` | `list[str]` | Heat exchangers |
| `COMPRESSORS` | `list[str]` | Compressors |
| `PUMPS` | `list[str]` | Pumps |
| `PIPES` | `list[str]` | Pipe segments |
| `HEATERS` | `list[str]` | Heaters |
| `COOLERS` | `list[str]` | Coolers |
| `SPREADSHEETS` | `dict[str, list[str]]` | `{spreadsheet name: [cells]}` |

!!! warning "Every variable must exist, even when empty"
    `main.py` passes all of them to `SimulationConnector.easy_setup()`, which reads each key directly. A missing key raises a `KeyError`. When you do not need a category, declare it empty (`PUMPS: list[str] = []`, `SPREADSHEETS: dict[str, list[str]] = {}`).

---



## Example

```python title="setup_subsep.py"
# -*- coding: utf-8 -*-

# Raw string (r"...") avoids problems with Windows backslashes
path_unisim = r"C:\path\to\file\simulation.usc"

SUBFLOWSHEETS: list[str] = []

MATERIAL_STREAMS: list[str] = ['feed_sep', 'liq sep', 'gas_sep', 'pump_1_in', 'pump_2_out']
MATERIAL_STREAMS_PHASE: list[str] = ['pump_1_in', 'pump_2_out']

FLASHTANKS: list[str] = ['V-100', 'V-101']
CONTROLLERS: list[str] = ['LIC-100', 'LIC-101', 'LIC-102']
VALVES: list[str] = ['VLV-100', 'VLV-101', 'Valve_bypass_1']
HEAT_EXCHANGERS: list[str] = ['E-100', 'E-100-2']
# 'pump_1' and 'pump_2' are of type compressor in UniSim, so they go here
COMPRESSORS: list[str] = ['pump_1', 'pump_2']

PUMPS: list[str] = []
PIPES: list[str] = []
HEATERS: list[str] = []
COOLERS: list[str] = []

SPREADSHEETS: dict[str, list[str]] = {
    'RGO': ['B24', 'F24'],
    'Pressure_boundary_condition': ['B2'],
}
```

!!! note
    In this case the equipment named `pump_1` and `pump_2` are of type **compressor** in UniSim, so they go in `COMPRESSORS`, not `PUMPS`. The name does not matter, the UniSim type does. See [Troubleshooting](#troubleshooting).

---

## Importing setup on main.py
The file can have any name. The example project uses `setup_example.py`, `main.py` imports it with:


=== "Explicit Variables Names"

    ```python title="on main.py"
    from setup_example import (
        path_unisim,
        pumps, valves, flashtanks, compressors, controllers,
        heat_exchangers, material_streams, material_streams_phase,
        heaters, coolers, pipes, spreadsheets, subflowsheets,
    )
    ```

=== "Implicit Variable Names"

    ```python title="on main.py"
    import setup_example
    ```


!!! info "Two ways to configure a project"
    - **Two-file mode** (this page): the configuration lives in `setup_*.py` and the logic in `main.py`.
    - **Single-file mode**: the same variables are declared at the top of `main.py`, as in `hv50_part1.py`. Nothing else changes, because the library receives the same lists either way. See [main.py](main.md#single-file-variant).

    Prefer two files when you reuse one script across several cases, and a single file for one-off experiments or parameter sweeps.



## Troubleshooting

When `build_objects()` cannot use a name, it **prints a message and removes the name from the list** instead of stopping. Check the console on the first run.

| Message | Cause | Fix |
|---|---|---|
| `'X' not found in <type> list.` | The name does not exist in the main flowsheet or in the listed subflowsheets | Check spelling, or add the subflowsheet to `SUBFLOWSHEETS` |
| `Wrong type for X: expected A, got B` | The object exists but is of another type | Move it to the correct list (e.g. from `PUMPS` to `COMPRESSORS`) |
| `Access failed for X: ...` | COM error while reading the object | Confirm the object is valid in the open case |
| `KeyError: 'pumps'` | A variable is missing from the setup | Declare it as an empty list |
