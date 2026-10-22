# Utilities Functions

These class lives in [`UnisimConnector.py`](../files/unisim-connector.md) as `Operation`. Each subclass (e.g., `Valves`, `Controllers`) only has to declare two things:



When configuring `setup.py`, it is often tedious to manually type out every valve, pump, or stream name. `SimulationConnector` provides a set of "getter" methods that scan the open UniSim case and return lists of available names for you.

These functions are available on your `Simulation` object in `main.py`, *after* `SimulationConnector` has been initialized (i.e., after the case is open).

## Discovering Operations by Type

You can get a list of names for a specific type of equipment using these methods:

| Method | Returns |
| :--- | :--- |
| `Simulation.get_valves()` | All objects names with `TypeName == 'valveop'` |
| `Simulation.get_pumps()` | All objects names with `TypeName == 'pumpop'` |
| `Simulation.get_compressors()` | All objects names with `TypeName == 'compressor'` |
| `Simulation.get_heatexchangers()` | All objects names with `TypeName == 'heatexop'` |
| `Simulation.get_flashtanks()` | All objects names with `TypeName == 'flashtank'` |
| `Simulation.get_controllers()` | All objects names with `TypeName == 'fbcontrolop'` |
| `Simulation.get_spreadsheets()` | All objects names with `TypeName == 'spreadsheetop'` |

## Discovering Streams and Subflowsheets

- **`Simulation.get_material_streams()`** — Returns a sorted list of all material stream names.
- **`Simulation.get_subflowsheets()`** — Returns a list of tuples: `(Name, TaggedName)` for every subflowsheet, as subflowsheets have a user defined `Name` but the simulator only sees the `TaggedName` for accessing it.

## Discovering Everything

If you want a complete map of the simulation, use:

- **`Simulation.get_all_operations()`** — Returns a dictionary where the keys are the `TypeName` strings (e.g., `'valveop'`, `'mixerop'`) and the values are lists of object names belonging to that type.


```python
ops = Simulation.get_all_operations()

# Get all valves
print(ops['valveop'])
# Output: ['VLV-100', 'VLV-101', 'VLV-102', ...]

# Print the whole dictionary
print(ops)

{
    'valveop': ['VLV-100', 'VLV-101', 'VLV-102', 'VLV-103', 'VLV-104', 'VLV-107', 'VLV-109', 'VLV-111', 'VLV-110', 'VLV-110-2', 'Valve_bypass_1', 'Valve_heat_1', 'VLV-106', 'Valve_bypass_2', 'Valve_heat_2', 'VLV-106-2', 'VLV-112', 'VLV-108'], 
    'flashtank': ['V-100', 'V-101'], 
    'pidfbcontrolop': ['LIC-100', 'LIC-101', 'LIC-102'], 
    'mixerop': ['MIX-100', 'MIX-102', 'MIX-102-2', 'MIX-101', 'MIX-101-2'], 
    'tankop': ['V-102'], 
    'compressor': ['pump_1', 'pump_2'], 
    'teeop': ['TEE-101', 'TEE-101-2', 'TEE-100', 'TEE-100-2', 'TEE-102'], 
    'heatexop': ['E-100', 'E-100-2'],
    'spreadsheetop': ['Pressure boundary condition'], 
    'pipeseg': ['PIPE-101', 'PIPE-102', 'PIPE-100']
}

```
!!! note "Case-dependent names"
    The names of the objects returned by these functions vary depending on the current case opened. A different .usc file will have a completely different set of equipment names, quantities, and even TypeName keys (for example, one case might have no teeop objects at all).

    Because of this, the lists in **[setup.py](../files/setup.md)** are specific to one simulation file. If you receive a new .usc file from a colleague, do not assume the old names in setup.py will work — use these utility functions to map out the new case first.

