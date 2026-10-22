# Main.py

`main.py` is the **entry point**. It holds the logic of one simulation run: open the case, choose what to record, advance the solver step by step, apply changes defined on the script, during the run, and finishing the simulation.



Run it from the project folder:

```bash
python main.py
```

---

## Execution flow

`main()` has six stages, always in this order:

| # | Stage | Call |
|---|---|---|
| 1 | Configure the run | constants at the top of `main()` |
| 2 | Open the case | `SimulationConnector(...)` |
| 3 | Declare what to record | `Simulation.easy_setup(...)` |
| 4 | *(optional)* Add properties | `Simulation.<group>.properties = {...}` |
| 5 | Validate names and create tables | `Simulation.build_objects(SUBFLOWSHEETS)` |
| 6 | Run and close | `Simulation.update(...)` in a loop, then `Simulation.finish(...)` |

!!! warning "Order matters"
    Properties added in stage 4 must be set **before** `build_objects()`. That call builds the property cache and creates the database tables, so a property added afterwards is not recorded.

---

## 1. Imports and path

```python title="main.py"
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)

from UnisimConnector import SimulationConnector
import setup_subsep
```

The three `sys.path` lines let Python find `UnisimConnector.py` when it sits **one folder above** the script. If `UnisimConnector.py` is in the same folder as `main.py`, they are not needed.

`script_dir` is also used to build output paths, so results are saved next to the script regardless of where you launch Python from.

---

## 2. Run configuration



```python title="main.py"
## SIMULATION CONFIG ##
OUTPUT_FOLDER = os.path.join(script_dir, 'folder_name') 
DB_NAME = os.path.join(script_dir, 'database_name.db')
# Good Practice is to explain the condition of the simulation on the tag
SIMULATION_TAG = 'opening_valve_condition_130bar70c'  

    # Simulation control
CONTINUE_SIMULATION = False    # Resume from last saved state if True  
SAVE_SIMULATION = False        # Save last simulation state to .usc file when finished 
SHOW_INTERFACE = True          # Display UniSim GUI during execution
EXPORT_CSV = False             # Export the data to csv file
```

| Constant | Effect |
|---|---|
| `OUTPUT_FOLDER` | Folder for `_simulation_summary.txt`, `_simulation_properties.txt` and CSV files. Created if it does not exist. |
| `DB_NAME` | SQLite file. Several runs can share it, since rows are separated by tag. |
| `SIMULATION_TAG` | Label stored in every row (`simulation_tag` column). **Use a different tag per run** that shares the same database. |
| `CONTINUE_SIMULATION` | `False` resets the solver integrator to its initial state. `True` continues from the state saved in the `.usc`. |
| `SAVE_SIMULATION` | `True` saves the case back to the `.usc` when the run finishes. |
| `SHOW_INTERFACE` | `True` shows the UniSim window. `False` runs hidden, which is useful for long batches. |
| `EXPORT_CSV` | `True` exports the recorded tables to CSV files when finishing. |



## 3. Opening the case and declaring what to record

```python title="main.py"
import os, sys, traceback
from UnisimConnector import SimulationConnector
import setup_subsep

script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.append(parent_dir)


Simulation = SimulationConnector(path_unisim, OUTPUT_FOLDER, SIMULATION_TAG,
                                 DB_NAME, CONTINUE_SIMULATION, SHOW_INTERFACE)

Simulation.easy_setup(
    pumps=setup_subsep.PUMPS, valves=setup_subsep.VALVES, flashtanks=setup_subsep.FLASHTANKS,
    compressors=setup_subsep.COMPRESSORS, controllers=setup_subsep.CONTROLLERS,
    heat_exchangers=setup_subsep.HEAT_EXCHANGERS,
    material_streams=setup_subsep.MATERIAL_STREAMS,
    material_streams_phase=setup_subsep.MATERIAL_STREAMS_PHASE,
    heaters=setup_subsep.HEATERS, coolers=setup_subsep.COOLERS, pipes=setup_subsep.PIPES,
    spreadsheets=setup_subsep.SPREADSHEETS,
)
```

Creating the `SimulationConnector` launches UniSim (or attaches to it), opens the `.usc`, and connects to the database. `easy_setup()` only **stores the names**. Nothing is read from UniSim until `build_objects()`.

All twelve arguments are required. See [setup.py](setup.md#expected-variables-in-the-file).

---

## 4. Adding properties that are not recorded by default

Each group has a default property list (for example, valves record `ActuatorPosition`, `PressureDrop`, `MassFlow`...). To record more, assign a dictionary of `{property: unit}`. Assigning **merges** with the defaults and does not replace them.

```python title="main.py"
Simulation.controllers.properties = {'Td': 'seconds', 'Ti': 'seconds', 'Gain': ''}

Simulation.heat_exchangers.properties = {
    'Lmtd': 'C',
    'ShellHeatTransferCoef': 'kJ/h-m2-C', 'TubeHeatTransferCoef': 'kJ/h-m2-C',
    'TubeSidePressureDrop': 'bar', 'ShellSidePressureDrop': 'bar',
    'UA': 'kJ/C-h',
}

Simulation.pipes.properties = {
    'SegmentLength': 'm', 'SegmentElevationChange': 'm',
    'SegmentOuterDiam': 'mm', 'SegmentInnerDiam': 'mm',
}
```

- Use `''` as the unit for dimensionless properties.
- The new property becomes a new column in the table. If the table already exists in an older database, the column is added automatically (`ALTER TABLE`).
- [Material streams](unisim-connector.md#materialstreams) have three separate dictionaries: `properties`, `phase_properties` and `components_properties`.

The default values and the available groups are listed in [Operations](../reference/operations-reference.md) and [Object Properties](../reference/properties-reference.md).

---

## 5. Building the objects

```python title="main.py"
try:
    Simulation.build_objects(SUBFLOWSHEETS)
except Exception as e:
    print(f"Initialization failed: {str(e)}")
    traceback.print_exc()
    return
```

This step checks each configured name against the case, creates the tables and **records the initial state (t = 0)**. Names that cannot be found are removed with a printed message (see [troubleshooting](setup.md#troubleshooting)).

!!! tip "Debugging breakpoint"
    The script has a `pass` line right after the parameters. Put a breakpoint there to inspect `Simulation.material_streams.names`, `Simulation.valves.objects` and so on before the loop starts.

---

## 6. Simulation loop

```python title="main.py"
TIME_STEP_SIZE = 0.033
TIME_STEP_UNIT = 'minutes'
N_SIM_STEPS = 2000

for current_step in range(N_SIM_STEPS):
    ...
    Simulation.update(TIME_STEP_SIZE, TIME_STEP_UNIT)
```

| Parameter | Meaning |
|---|---|
| `TIME_STEP_SIZE` | Simulated time advanced per step |
| `TIME_STEP_UNIT` | `'seconds'`, `'minutes'`, or `'hr'` |
| `N_SIM_STEPS` | Number of steps. Total simulated time is `TIME_STEP_SIZE × N_SIM_STEPS` (here ≈ 66 minutes) |

!!! note "Minimum step"
    The UniSim sample time has a lower limit of 2 seconds (≈ 0.033 min). Smaller values are reset to that limit.

Each `update()` call **advances the solver** (`RunFor`) and then **writes one row per tracked object** to the database.

### Applying disturbances

Put changes **before** `Simulation.update(...)`, so they take effect during that step. Objects are accessed by name:

```python title="main.py"
if current_step == 3:                                              # after 3 steps
    Simulation.controllers['LIC-100'].SP.SetValue(60, 'bar')       # change a setpoint
    Simulation.valves['VLV-100'].ActuatorPosition.SetValue(100, '%')  # open a valve
```

!!! danger "Do not use `continue` for disturbances"
    The example in the script has `if current_step == 3: continue`. A `continue` jumps to the next iteration **without calling `update()`**, so that step is not simulated and nothing is recorded for it. Use the `if` block to *change* values and let the loop reach `update()`.

Reading and writing follow the same pattern:

```python
Simulation.material_streams['stream_name'].Temperature.GetValue('C')
Simulation.controllers['LIC-100'].PV.GetValue('')
Simulation.valves['VLV-100'].ActuatorPosition.SetValue(50, '%')
```

If you are unsure about the unit, use `GetValue('')`. For other ways to explore the UniSim object model, see [COM Navigation](../reference/com-navigation.md).

### Error handling

```python title="main.py"
try:
    Simulation.update(TIME_STEP_SIZE, TIME_STEP_UNIT)
except Exception as e:
    simulation_aborted = True
    traceback.print_exc()
```

An error stops the loop and sets `simulation_aborted`. The data recorded until that moment is already in the database, because rows are committed at every step.

---

## 7. Finishing

```python title="main.py"
quit_unisim = not simulation_aborted
Simulation.finish(quit_unisim, SAVE_SIMULATION, EXPORT_CSV)
```

| Outcome | `quit_unisim` | Result |
|---|---|---|
| Completed | `True` | UniSim is closed |
| Aborted | `False` | UniSim stays open so you can inspect the case |

`finish()` writes the summary and units files, optionally the CSV files, closes the database and (if requested) closes UniSim. Details in [UnisimConnector.py](unisim-connector.md#finishing-a-run).

!!! warning "Pass the arguments in the right order"
    The signature is `finish(quit_unisim, save_simulation, export_csv)`. Calling `finish(quit_unisim, EXPORT_CSV)` sends the CSV flag to `save_simulation`. Keyword arguments avoid this mistake:

    ```python
    Simulation.finish(quit_unisim=True, save_simulation=SAVE_SIMULATION, export_csv=EXPORT_CSV)
    ```

---

## Single-file variant

`hv50_part1.py` shows the same flow with the setup declared **inside** the script and extra logic for experiments. The differences are:

- The lists are lowercase variables at the top of the file (`valves = [...]`, `spreadsheets = {...}`), with no `import setup`.
- A `for` loop over a parameter grid (`combvec(bp1_positions, bp2_positions)`) creates **one `SimulationConnector` per scenario**, each with its own tag (`bp1_50.0-bp2_20.0`) but the same database.
- A background **timeout monitor** thread kills UniSim if a step takes too long (`persistent_timeout_monitor`, `run_simulation_step`).
- `slew_rate_filter` generates smooth ramps for actuator changes instead of abrupt steps.
- Each scenario appends a line to `simulation_logs.txt` (success time or failure) and optionally saves the case with `Simulation.case.SaveAs(...)`.

These helper functions are described in [Utilities Functions](../reference/utilities-functions.md).

