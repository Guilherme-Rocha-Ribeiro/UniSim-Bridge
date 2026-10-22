# -*- coding: utf-8 -*-
# @author: Guilherme Ribeiro, Daniel Diniz, Raony Fontes


import win32com.client as winclt                    # pip install pywin32
import pandas as pd                                 # pip install pandas
from os import path, makedirs, system, PathLike     
from warnings import warn
import traceback
import sqlite3
from datetime import date
# from time import sleep


def _normalize_time_value(t):
    """Return a float time value from various possible inputs.

    Handles scalars, lists/tuples, and pandas Series by extracting a representative
    scalar and converting to float when possible. Returns None if conversion fails.
    """
    try:
        import pandas as _pd
    except Exception:
        _pd = None

    # pandas Series -> take first element if present
    if _pd is not None and isinstance(t, _pd.Series):
        try:
            if len(t) > 0:
                t = t.iat[0]
            else:
                return None
        except Exception:
            return None

    # lists/tuples -> take first element
    if isinstance(t, (list, tuple)):
        if len(t) > 0:
            t = t[0]
        else:
            return None

    # Try to coerce to float
    try:
        return float(t) if t is not None else None
    except Exception:
        return None



def binary_search(array: list[str], key: str) -> bool:
    inicio = 0
    fim = len(array) - 1
    while inicio <= fim:
        meio = (inicio + fim)//2
        if array[meio] == key:
            return True
        elif array[meio] < key:
            inicio = meio + 1
        else:
            fim = meio -1
    return False

class Operation:
    """""
    Methods:
        -> _build_object(name_list, unisim_asset_collection): Build and validate operation objects from a name list.
        -> _build_data(time): Collect and store property data for all tracked objects at a given time.
        -> _load_data(): Load operation data from CSV files.
        -> _concat_data(time): Concatenate new property data to existing DataFrames.
        -> _save_data(simulation_file_path): Save operation data to CSV files.
        -> names (property): Get or extend the list of tracked operation names.
        -> properties (property): Get or update the dictionary of tracked properties and their units.
        -> __getitem__(name): Access a tracked operation object by name.
    
    """
    def __init__(self, db_conn: sqlite3.Connection, db_tag: str, cursor: sqlite3.Cursor):
        self._operation_title = 'Operation'            # Will be overridden by subclasses own operation_title
        self._names: list[str] = []                    # Names from the easy setup and than check if it exists on the simulation file
        self.objects: dict[str, winclt.CDispatch] = {} # Stores unisim COMObject keyed by object name
        self.data = {}                                 # Stores DataFrames keyed by object name
        self._properties: dict[str, str] = {} 

        self.db_conn = db_conn
        self.cursor = cursor
        self.db_tag = db_tag

        self.comObjs_properties = {}

    def get_table_name(self) -> str:
        table_name = self._operation_title
        if table_name == 'materialstream':
            table_name = 'materialstream_properties'

        return table_name

    def _build_object(self, name_list: list[str], unisim_operation_object: winclt.CDispatch, unisim_subflow_op_object: list[winclt.CDispatch]) -> None:
        
        """
        Builds and validates operation objects from a name list against a UniSim collection.
        Populates self.objects with valid UniSim COM objects.
        Modifies name_list in-place by removing names for which objects could not be built.
        """
        search_list: list[str] = sorted({n.upper() for n in unisim_operation_object.Names})
        
        for name in name_list.copy():
            if binary_search(search_list, name.upper()):
                try:
                    if unisim_operation_object[name].TypeName in self._operation_title:
                        self.objects[name] = unisim_operation_object.Item(name)
                    else:
                        print(f"Wrong type for {name}: expected {self._operation_title}, got {unisim_operation_object[name].TypeName}")
                        name_list.remove(name)
                except Exception as e:
                    print(f"Access failed for {name}: {str(e)}")
                    name_list.remove(name)
            else:
                access_error_control = 0
                for operation in unisim_subflow_op_object:
                    try:
                        if operation[name].TypeName in self._operation_title:
                            self.objects[name] = operation.Item(name)
                        else:
                            print(f"Wrong type for {name}: expected {self._operation_title}, got {operation[name].TypeName}")
                            name_list.remove(name)
                    except:
                        access_error_control+=1

                if access_error_control == len(unisim_subflow_op_object):
                    print(f"'{name}' not found in {self._operation_title} list.")
                    name_list.remove(name)

    def build_properties_cache(self):
        """       """
        
        for name, obj in self.objects.items():
            self.comObjs_properties[name] = {}
            for prop_name, unit in self.properties.items():
                try:
                    prop_object = getattr(obj, prop_name)
                    self.comObjs_properties[name][prop_name] = (prop_object, unit)
                except:
                    continue


    def _build_data(self, time: float) -> None:
        self.build_properties_cache()
        self.create_operation_table()
        self._update_data(time)

    def _update_data(self, time: float) -> None:
        self.data = {}

        for name in self.objects.keys():
            setup_properties = {'time': time}
            for prop, (obj, unit) in self.comObjs_properties[name].items():
                try:
                    setup_properties.update({prop: obj.GetValue(unit)})
                except:
                    setup_properties.update({prop: None})
                
            self.data[name] = setup_properties
            self._insert_row_to_db(self.data)
        
    def _insert_row_to_db(self, data: dict):
        columns = ['name', 'time', 'simulation_tag', 'date', *list(self.properties.keys())]
        
        all_values = []
        for name, data_ in data.items():
            values = (
                name,
                f"{data_['time']:.4f}",  
                self.db_tag,
                date.today().strftime('%d-%m-%Y'),
                *[data_[prop] for prop in self.properties.keys()]  # Direct values
            )
            all_values.append(values)
        
        if all_values:
            placeholders = ', '.join(['?'] * len(columns))
            update_set = ', '.join([f"{col}=excluded.{col}" for col in self.properties.keys()])
            
            query = f"""
                INSERT INTO {self.get_table_name()} ({', '.join(columns)}) 
                VALUES ({placeholders})
                ON CONFLICT(name, time, simulation_tag) DO UPDATE SET 
                {update_set}
            """
            self.cursor.executemany(query, all_values)
        
        self.db_conn.commit()


    def create_operation_table(self):
        
        columns = ["name TEXT", "time REAL", "simulation_tag TEXT", "date TEXT"] + [f"{prop} REAL" for prop in self.properties.keys()]
        
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.get_table_name()} ({', '.join(columns)},
        PRIMARY KEY (name, time, simulation_tag))
        """
        self.cursor.execute(create_sql)

        self.cursor.execute(f"PRAGMA table_info({self.get_table_name()})")
        current_table_columns = []
        for row in self.cursor.fetchall():
            current_table_columns.append(row[1])

        for prop in list(self.properties.keys()):
            if prop not in current_table_columns:
                add_column = f"ALTER TABLE {self.get_table_name()} ADD COLUMN {prop} REAL"
                self.cursor.execute(add_column)
                print(f"new column added to {self.get_table_name()} {prop}")


        self.db_conn.commit()

    def _save_to_csv(self, output_folder):
        """
        Combined function that fetches data from database and saves to CSV if requested.
        """
        
        # Get column names excluding simulation_tag
        self.cursor.execute(f"PRAGMA table_info({self.get_table_name()})") 
        column_names = []
        for row in self.cursor.fetchall():
            if row[1] != 'simulation_tag':
                column_names.append(row[1])
        
        # Fetch data from database
        query = f"SELECT {', '.join(column_names)} FROM {self.get_table_name()} WHERE simulation_tag = ?"
        self.cursor.execute(query, (self.db_tag,))
        results = self.cursor.fetchall()
        
        # Create DataFrame only if there are results
        if results:
            results_df = pd.DataFrame(results, columns=column_names)
            results_df.set_index('name', inplace=True)
            
            # Save to CSV
            results_df.to_csv('{}{}_{}_data.csv'.format(output_folder, self.db_tag.upper(), self.get_table_name()))
            
            # Keep df on the instance 
            self.df =  results_df
            

    @property
    def names(self) -> list[str]:
        """List of object names."""
        return self._names
      
    @names.setter
    def names(self, list: list[str]) -> None:
        """Add objects to the tracking list."""
        self._names.extend(list)

    @property
    def properties(self) -> dict[str, str]:
        """Dictionary of properties and their units."""
        return self._properties

    @properties.setter
    def properties(self, property_with_unit: dict[str, str]) -> None:
        """Update properties dictionary."""
        self._properties.update(property_with_unit)
    
    def __getitem__(self, name: str) -> winclt.CDispatch:
        if name not in self.objects:
            raise KeyError(f"'{name}' not found in objects.")
        else:
            return self.objects[name]


class StreamComponents:
    def __init__(self, component_names: list, com_object: winclt.CDispatch):
        self.component_names = component_names
        self.obj = com_object
        self.data = {}       

    def _update_data(self, time: float) -> None:
        for prop, (obj, unit) in self.obj.items():
            try:
                values = obj.GetValues(unit) 
                self.data[prop] = {
                    'time': time, 
                    **dict(zip(self.component_names, values))
                }
            except:
                self.data[prop] = {
                    'time': time, 
                    **{comp: None for comp in self.component_names}
                }
                
  
class MaterialStreams(Operation):
    phase_types = ['VapourPhase', 'LightLiquidPhase', 'HeavyLiquidPhase']
    
    def __init__(self, db_conn, db_tag, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'materialstream'

        self.properties = dict(
            Pressure='bar', StdGasFlow='STD_m3/h', MassFlow='kg/h', MolarFlow='kgmole/h',
            StdLiqVolFlow='m3/h', Temperature='C', MassDensity='kg/m3', VapourFraction='',
            ActualGasFlow='ACT_m3/h', ActualLiqFlow='m3/h', ActualVolumeFlow='m3/h'
        )

        self._components_properties = dict(ComponentMassFlow ='kg/h', ComponentMolarFlow ='kgmole/h', ComponentMolarFraction ="", ComponentMassFraction ="")

        self._phase_properties = dict(MassFlow='kg/h', MolarFlow='kgmole/h', MassDensity='kg/m3', ActualVolumeFlow='m3/h', Viscosity='cP', PhaseFraction='')
        
        self.collected_phases: list[str] = []
        
        self.comObjs_components: dict[str, dict[str, tuple(winclt.CDispatch, str)]] = {}
        self.stream_components = {}
        
        self.comObjs_phases: dict[str, dict[str, tuple(winclt.CDispatch, str)]] = {} 
        self.phases = {}

        self.comp_names = []
        

    def build_phase_cache(self):
        for name in self.collected_phases:
            # Initialize the nested structure for this name first
            self.comObjs_phases[name] = {}
            
            for phase in MaterialStreams.phase_types:
                self.comObjs_phases[name][phase] = {}
                self.comObjs_phases[name][phase]['properties'] = {}
                self.comObjs_phases[name][phase]['object'] = {}
                
                for prop_name, unit in self._phase_properties.items():
                    try:
                        phase_obj = getattr(self.objects[name].GetFluid(), phase)
                        prop_object = getattr(phase_obj, prop_name)

                        self.comObjs_phases[name][phase]['object'] = phase_obj
                        self.comObjs_phases[name][phase]['properties'][prop_name] = (prop_object, unit)
                    except AttributeError as e:
                        print(f"Error accessing {phase}.{prop_name} for {name}: {e}")
                    continue


    def build_components_cache(self):
        for name, obj in self.objects.items():
            self.comObjs_components[name] = {}
            for prop_name, unit in self._components_properties.items():
                try:
                    prop_object = getattr(obj, prop_name)
                    self.comObjs_components[name][prop_name] = (prop_object, unit)
                except:
                    continue

    def build_properties_cache(self):
        return super().build_properties_cache()

    def _build_data(self, time: float) -> None:
        self.build_components_cache() # only for main material stream comp 
        self.build_phase_cache()
        generic_stream = list(self.objects)[0] 
        self.comp_names = list(self.objects[generic_stream].GetFluid().Components.Names)
        self._create_main_components_table()
        
        
        for name in self.objects.keys():
            self.stream_components[name] = StreamComponents(self.comp_names, self.comObjs_components[name])
            if name in self.collected_phases:
                self.phases[name] = self.Phase(
                    self.comObjs_phases[name], name, self.db_conn, self.db_tag, self.comp_names
                )

        super()._build_data(time) 
        self._update_data(time)

    def _update_data(self, time: float) -> None:
        """
        The Workhorse: Updates data for the main stream and delegates to phase handlers.
        """
        # 1. Update and write the main stream's bulk properties
        super()._update_data(time)
        
        for name in self.objects.keys():
            # 2. Update the main stream's component data snapshot
            self.stream_components[name]._update_data(time) # stream compents obj , self.components_objects[name]
            
            # 3. Write that component snapshot to the database
            self._insert_main_stream_components_to_db(name)
            
            if name in self.collected_phases:
                self.phases[name]._update_data(time)

    def _create_main_components_table(self):
        """Creates the single table for overall stream compositions."""

        formated_names = [f"'{comp}'" for comp in self.comp_names]
        columns = ["stream_name TEXT","time REAL", "simulation_tag TEXT", "property_type TEXT", *formated_names] 

        create_table = f"""
        CREATE TABLE IF NOT EXISTS materialstream_components ({', '.join(columns)},
        PRIMARY KEY (stream_name, time, simulation_tag, property_type))
        """

        self.cursor.execute(create_table)
        self.db_conn.commit()


    def _insert_main_stream_components_to_db(self, stream_name: str):
        """Writes the overall stream component data to its specific table."""
        formated_names = [f'"{comp}"' for comp in self.comp_names]
        for prop in self.stream_components[stream_name].data.keys():
            values = [stream_name, f"{self.stream_components[stream_name].data[prop]['time']:.4f}", self.db_tag, prop, *[self.stream_components[stream_name].data[prop][component] for component in self.comp_names]] 
            placeholders = ', '.join(['?'] * len(values))
                
            columns = ['stream_name', 'time', 'simulation_tag' ,'property_type', *formated_names]
                
            query = f"""
            INSERT OR IGNORE INTO materialstream_components ({', '.join(columns)}) 
            VALUES ({placeholders})
            """
            self.cursor.execute(query, values)
        
        self.db_conn.commit()

    def _save_to_csv(self, output_folder):
        super()._save_to_csv(output_folder) # main material_stream properties
        
        temp_df = pd.read_sql(f"SELECT * FROM materialstream_components WHERE simulation_tag = '{self.db_tag}'", self.db_conn)
        temp_df.drop(columns=['simulation_tag'])
        temp_df.to_csv('{}{}_{}_data.csv'.format(output_folder , self.db_tag.upper(), 'materialstream_components'), index=False)

        
        suffix_list = ['components', 'properties']
        for phase in MaterialStreams.phase_types:
            for suffix in suffix_list:
                table_name = f"{phase.lower()}_{suffix}"
                query = f"SELECT * FROM {table_name} WHERE simulation_tag = '{self.db_tag}'"
                temp_df = pd.read_sql_query(query, self.db_conn)
                temp_df.drop(columns=['simulation_tag'])

                temp_df.to_csv('{}{}_{}_data.csv'.format(output_folder , self.db_tag.upper(), table_name), index=False)


    @property
    def phase_properties(self) -> dict[str, str]:
        """Dictionary of properties and their units."""
        # It gets/sets the PRIVATE attribute
        return self._phase_properties

    @phase_properties.setter
    def phase_properties(self, property_with_unit: dict[str, str]) -> None:
        """Update properties dictionary."""
        # It gets/sets the PRIVATE attribute
        self._phase_properties.update(property_with_unit)

    
    # The property is PUBLIC (no underscore)
    @property
    def components_properties(self) -> dict[str, str]:
        """Dictionary of properties and their units."""
        # It gets/sets the PRIVATE attribute
        return self._components_properties

    @components_properties.setter
    def components_properties(self, property_with_unit: dict[str, str]) -> None:
        """Update properties dictionary."""
        # It gets/sets the PRIVATE attribute
        self._components_properties.update(property_with_unit)


    class Phase:
        """
        Manages all data and database I/O for the phases of a single material stream
        using a memory-optimized architecture.
        """
        def __init__(self, stream_object, stream_name: str, db_conn, db_tag, comp_names):
            self.db_conn = db_conn
            self.db_tag = db_tag
            self.object = stream_object  
            self._stream_name = stream_name
            self.comp_names = comp_names
            
            
            self.data: dict[str, pd.DataFrame] = {}           # In-memory snapshot for properties
            self.components: dict[str, StreamComponents] = {} # In-memory snapshot for components

            # Initialize a StreamComponents handler for each potential phase
            comp_props = dict(MassFractions="", MolarFractions="")

            self.comObjs_cache = {}
            for phase_name in self.object.keys():  
                self.comObjs_cache[phase_name] = {}  
                
                for prop, unit in comp_props.items():
                    prop_obj = getattr(self.object[phase_name]['object'], prop)
                    self.comObjs_cache[phase_name][prop] = (prop_obj, unit)
                
                self.components[phase_name] = StreamComponents(
                    comp_names,
                    self.comObjs_cache[phase_name]
                )

            self._create_tables()

        def _create_tables(self):
            """Creates all necessary tables for each phase if they don't exist."""
            cursor = self.db_conn.cursor()

            # check columns names
            desired_columns = ['stream_name', 'time', 'simulation_tag'] + list(self.object['VapourPhase']['properties'].keys())
            
            formated_names = [f"'{comp}'" for comp in self.comp_names]
            
            for phase in self.object.keys():
                # Create phase properties table
                table_name = f"{phase.lower()}_properties"
                
                properties_cols = ["stream_name TEXT", "time REAL", "simulation_tag TEXT"] + [f'"{prop}" REAL' for prop in self.object['VapourPhase']['properties'].keys()]
                cursor.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(properties_cols)}, PRIMARY KEY (stream_name, time, simulation_tag))')
                
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_columns = [col[1] for col in cursor.fetchall()]
                
                for column in desired_columns:
                    if column not in existing_columns:
                        try:
                            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column} REAL")
                            print(f"Added column '{column}' to table '{table_name}'")
                        except sqlite3.OperationalError as e:
                            print(f"Error adding column '{column}' to '{table_name}': {e}")
                
                # Create phase components table
                table_comps = f"{phase.lower()}_components"
                components_cols = ["stream_name TEXT", "time REAL", "simulation_tag TEXT", "property_type TEXT"] + formated_names
                cursor.execute(f'CREATE TABLE IF NOT EXISTS "{table_comps}" ({", ".join(components_cols)}, PRIMARY KEY (stream_name, time, simulation_tag, property_type))')
            
            self.db_conn.commit()

        def _build_data(self, time: float) -> None:
            """Initializer: Simply calls the main update method for the first data point."""
            self._update_data(time)

        def _update_data(self, time: float) -> None:
            for phase_name in self.object.keys():
                
                setup_properties = {'time': time}
                for prop ,(obj, unit) in self.object[phase_name]['properties'].items():
                    try:
                        setup_properties.update({prop: obj.GetValue(unit)})
                    except:
                        setup_properties.update({prop: None})

                
                self.data[phase_name] = setup_properties
                self._insert_properties_to_db(phase_name, setup_properties)

                # --- 2. Handle Phase Components ---
                component_holder = self.components[phase_name]
                component_holder._update_data(time)
                self._insert_components_to_db(phase_name, component_holder)

        def _insert_properties_to_db(self, phase_name: str, prop_dict):
            """Writes a row of phase properties to the correct DB table."""
            table_name = f"{phase_name.lower()}_properties"
            
            cursor = self.db_conn.cursor()
            values = [self._stream_name, prop_dict['time'], self.db_tag] + [prop_dict[prop] for prop in prop_dict.keys()]
            
            
            
            columns = ['stream_name', 'time', 'simulation_tag', *list(prop_dict.keys())] 
                
            placeholders = ', '.join(['?'] * len(values))
            update_set = ', '.join([f"{col}=excluded.{col}" for col in prop_dict.keys()])
                
            query = f"""
                    INSERT INTO {table_name} ({', '.join(columns)}) 
                    VALUES ({placeholders})
                    ON CONFLICT(stream_name, time, simulation_tag) DO UPDATE SET 
                    {update_set}
                """

            cursor.execute(query, values)
            self.db_conn.commit()

        def _insert_components_to_db(self, phase_name: str, component_holder: StreamComponents):
            """Reads from the StreamComponents snapshot and writes to the DB."""
            table_name = f"{phase_name.lower()}_components"
            
            formated_names = [f"'{comp}'" for comp in component_holder.component_names]

            cursor = self.db_conn.cursor()
            for prop_type, keys in component_holder.data.items():
                columns = ['stream_name', 'time', 'simulation_tag', 'property_type'] + formated_names
                values = [self._stream_name, keys['time'], self.db_tag, prop_type] + [keys[comp] for comp in component_holder.component_names]
                
                placeholders = ', '.join(['?'] * len(values))
                    
                query = f"""
                INSERT OR IGNORE INTO {table_name} ({', '.join(columns)}) 
                VALUES ({placeholders})
                """

                cursor.execute(query, values)
            self.db_conn.commit()

        # @property
        # def properties(self):
        #     return self._properties
        
  
class Spreadsheets:
    def __init__(self, db_conn, db_tag, cursor):
        self._operation_title = 'spreadsheetop'
        self.cells = {}
        self.objects = {}
        self.data = {}
        self.db_conn = db_conn
        self.db_tag = db_tag
        self.cursor = cursor

    @property
    def names(self):
        return list(self.cells.keys())

    def _build_object(self, cells_list: dict, unisim_operation_object: winclt.CDispatch, unisim_subflow_op_object: list[winclt.CDispatch]) -> None:
        for name in cells_list.copy().keys():
            search_list: list[str] = sorted(n.upper() for n in unisim_operation_object.Names)
            if binary_search(search_list, name.upper()):
                try:
                    if unisim_operation_object[name].TypeName in self._operation_title:
                        self.objects[name] = unisim_operation_object.Item(name)
                    else:
                        print(f"Wrong type for {name}: expected {self._operation_title}, got {unisim_operation_object[name].TypeName}")
                        del cells_list[name]
                except Exception as e:
                    print(f"Access failed for {name}: {str(e)}")
                    del cells_list[name]
            else:
                access_error_control = 0
                for operation in unisim_subflow_op_object:
                    try:
                        if operation[name].TypeName in self._operation_title:
                            self.objects[name] = operation.Item(name)
                        else:
                            print(f"Wrong type for {name}: expected {self._operation_title}, got {operation[name].TypeName}")
                            del cells_list[name]
                    except:
                        access_error_control+=1

                if access_error_control == len(unisim_subflow_op_object):
                    print(f"'{name}' not found in {self._operation_title} list.")
                    del cells_list[name]

    def create_table(self) -> None:
        
        columns = ["cell TEXT" ,"time REAL", "simulation_tag TEXT", "date TEXT"] + ["value"]
        for name in self.cells.keys():
            create_sql = f"""
                CREATE TABLE IF NOT EXISTS spreadsheet_{name.upper()} ({', '.join(columns)},
                PRIMARY KEY (cell, time, simulation_tag))
                """
            self.cursor.execute(create_sql)

            self.db_conn.commit()


    def _build_data(self, time: float) -> None:
        self.create_table()
        self._update_data(time)


    def _update_data(self, time: float) -> None:
        self.data = {}
        for name, cells in self.cells.items():
            setup_data = {'time': [time]}
            for cell in cells:
                try:
                    setup_data[cell] = [self.objects[name].Cell(cell).CellValue]
                except Exception as e:
                    print(f"Error accessing cell {cell} in {name}: {str(e)}")
                    setup_data[cell] = [None]


            self.data[name] = pd.DataFrame(setup_data)
            self._insert_row(self.data)
        
    
    def _insert_row(self, data):
        
        columns = ["cell", "time", "simulation_tag", "date", "value"]
        
        for name, df in data.items():
            # Validate/sanitize table name
            table_name = f"spreadsheet_{name.upper()}"
            
            rows_to_insert = []
            for _, row in df.iterrows():
                time_val = f"{row['time']:.4f}"
                date_val = date.today().strftime('%d-%m-%Y')
                for col_name, value in row.items():
                    if col_name == 'time':
                        continue

                    rows_to_insert.append((
                            col_name,      # cell
                            time_val,      # time
                            self.db_tag,   # simulation_tag
                            date_val,      # date
                            value          # value
                        ))
                
            if rows_to_insert:
                placeholders = ', '.join(['?'] * len(columns))
                update_columns = ["value", "date"]
                update_set = ', '.join([f"{col}=excluded.{col}" for col in update_columns])
                
                query = f"""
                    INSERT INTO {table_name} ({', '.join(columns)}) 
                    VALUES ({placeholders})
                    ON CONFLICT(cell, time, simulation_tag) DO UPDATE SET 
                    {update_set}
                """
                
                self.cursor.executemany(query, rows_to_insert) 
                
                self.db_conn.commit()
    
    # def _save_to_csv(self, output_folder):
        
                

# class Tees(Operation):
#     def __init__(self, db_conn: sqlite3.Connection, db_tag: str):
#         super().__init__(db_conn, db_tag)
#         self._operation_title = ('teeop')
#         self.properties = dict(

#         )
    
    # AttachedProducts 
    # Simulation.case.Flowsheet.Operations['TEE-100'].AttachedProducts.Item('8')
    # Simulation.case.Flowsheet.Operations['TEE-100'].AttachedProducts.Item('8').TypeName = 'materialstream'

# class Tanks(Operation):
#     def __init__(self, db_conn: sqlite3.Connection, db_tag: str):
#         super().__init__(db_conn, db_tag)
#         self._operation_title = ('tankop')


class Pipesegs(Operation):
    def __init__(self, db_conn: sqlite3.Connection, db_tag: str, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'pipeseg'
        self.properties = dict(
            PressureDrop='kPa'
        )
    
    def _update_data(self, time: float) -> None:
        for name in self.objects.keys():
            setup_properties = {'time': [time]}
            for prop in self.properties.keys():
                obj = getattr(self.objects[name], prop)
                try:
                    # Try GetValue first
                    value = obj.GetValue(self.properties[prop])
                    setup_properties[prop] = [value]
                except AttributeError:
                    try:
                        # Fall back to GetValues
                        values = obj.GetValues(self.properties[prop])
                        sum = 0
                        for value in values:
                            sum += value
                        setup_properties[prop] = [sum]
                    except Exception as e:
                        setup_properties.update({prop: [None]})


            self.data[name] = pd.DataFrame(setup_properties)
            self._insert_row_to_db(self.data)


class Heaters(Operation):
    def __init__(self, db_conn: sqlite3.Connection, db_tag: str, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'heaterop'
        self.properties = dict(
            MassFlow='kg/h',
            FeedTemperature= 'C',
            FeedPressure='bar', 
            ProductTemperature = 'C'
        )


class Coolers(Operation):
    def __init__(self, db_conn: sqlite3.Connection, db_tag: str, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'coolerop'
        self.properties = dict(
            MassFlow='kg/h',
            FeedTemperature= 'C',
            FeedPressure='bar', 
            ProductTemperature = 'C'
        )

class Flashtanks(Operation):
    def __init__(self, db_conn, db_tag, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'flashtank'
        self.properties = dict(
            VesselPressure='kPa',
            VesselTemperature='C'
        )

class Compressors(Operation):
    def __init__(self, db_conn, db_tag, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'compressor'
        self.properties = dict(
            MassFlow='kg/h',
            FeedTemperature='C',
            FeedPressure='bar',
            CompressorSpeed='rpm',
            CompAdiabaticEff='',
            AdiabaticHead='m',
            Energy='kw',
            PressureIncrease='kPa'
        )

class Controllers(Operation):
    def __init__(self, db_conn, db_tag, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'pidfbcontrolop'
        self.properties = dict(
            SP='',   
            PV='',
            OP='',
            RampDuration='',
        )

class HeatExchangers(Operation):
    def __init__(self, db_conn, db_tag, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'heatexop'
        self.properties = dict(
            Duty='kJ/h'
        )

class Pumps(Operation):
    def __init__(self, db_conn, db_tag, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'pumpop'
        self.properties = dict(
        )

class Valves(Operation):
    def __init__(self, db_conn, db_tag, cursor):
        super().__init__(db_conn, db_tag, cursor)
        self._operation_title = 'valveop'
        self.properties = dict(
            ActuatorPosition='%',
            PressureDrop='bar',
            FeedTemperature='C',
            FeedPressure='bar',
            MolarFlow='kgmole/h',
            MassFlow='kg/h'
        )

class SimulationConnector:

    def __init__(self, file_path_unisim, OUTPUT_FOLDER, db_tag, db_name:str = 'Simulation.db', continue_simulation: bool = True, case_visible: bool = True):
        self.OUTPUT_FOLDER = OUTPUT_FOLDER
        self._simulation_name = path.basename(file_path_unisim)
        self._continue_simulation = continue_simulation
        self.db_conn = sqlite3.connect(db_name)
        self.db_tag = db_tag
        self.cursor = self.db_conn.cursor()
        
        self._simulation_abort = False

        
        self.cursor.execute("PRAGMA synchronous = NORMAL ")  #
        self.cursor.execute("PRAGMA journal_mode = WAL")    # Does not create journal file
        self.cursor.execute("PRAGMA cache_size = -262144")  # ~256MB cache: If the argument N is negative, then the number of cache pages is adjusted to be a number of pages that would use approximately abs(N*1024) bytes of memory   


        if not path.exists(self.OUTPUT_FOLDER):
            makedirs(self.OUTPUT_FOLDER)

        self.unisim = winclt.Dispatch("UnisimDesign.Application")
        self.case = self.unisim.SimulationCases.Open(file_path_unisim)
        self.case.visible = 1 if case_visible else 0

        self.process_id = self.unisim.CurrentProcessID
        
        
        self.integrador = self.case.Solver.Integrator
        self.integrador.Mode = 0
        if not self._continue_simulation:
            self.integrador.Reset()

        # Initialize all component classes with db_conn
        self.material_streams = MaterialStreams(self.db_conn, self.db_tag, self.cursor)
        self.valves = Valves(self.db_conn, self.db_tag, self.cursor)
        self.pumps = Pumps(self.db_conn, self.db_tag, self.cursor)
        self.pipes = Pipesegs(self.db_conn, self.db_tag, self.cursor)
        self.heat_exchangers = HeatExchangers(self.db_conn, self.db_tag, self.cursor)
        self.compressors = Compressors(self.db_conn, self.db_tag, self.cursor)
        self.controllers = Controllers(self.db_conn, self.db_tag, self.cursor)
        self.flashtanks = Flashtanks(self.db_conn, self.db_tag, self.cursor)
        self.coolers = Coolers(self.db_conn, self.db_tag, self.cursor)
        self.heaters = Heaters(self.db_conn, self.db_tag, self.cursor)
        self.spreadsheets = Spreadsheets(self.db_conn, self.db_tag, self.cursor)

    
        self.operations = [
            self.pipes, self.pumps, self.valves,
            self.flashtanks, self.compressors, 
            self.controllers, self.heat_exchangers, self.coolers, self.heaters
        ]


    def _validate_tagname(self):
        pass
        # if self.db_tag

    def _validate_list_of_strings(value, param_name: str):
        """Validate that value is a list of strings"""
        if not isinstance(value, list):
            raise TypeError(
                f"\nOn setup.py: '{param_name.upper()}' must be a list[str], but got {type(value).__name__}.\n"
                f"Example: {param_name.upper()} = ['item1','item2']"
            )

        if not all(isinstance(item, str) for item in value):
            raise TypeError(f"\nOn setup.py: All items in '{param_name.upper()}' list must be strings")

    def _validate_spreadsheets_dict(value, param_name: str):
        """Validate that value is a dict with str keys and list[str] values"""
        if not isinstance(value, dict):
            raise TypeError(
                f"\nOn setup.py: '{param_name.upper()}' must be a dict[str, list[str]], got {type(value).__name__}\n"
                f"Example: SPREADSHEETS = dict(spreadsheet_name: ['cell_1', 'cell_2'])"
                )
        
        for key, val in value.items():
            if not isinstance(key, str):
                raise TypeError(f"On setup.py All keys in '{param_name.upper()}' must be strings")
            SimulationConnector._validate_list_of_strings(val, f"{param_name.upper()}['{key}']")

    def easy_setup(self,**kwargs):
        for operation_title, value in kwargs.items():
            if operation_title != 'spreadsheets':
                SimulationConnector._validate_list_of_strings(value, operation_title)
            else:
                SimulationConnector._validate_spreadsheets_dict(value, operation_title)
                    

        self.pumps.names = list(set(kwargs['pumps']))
        self.valves.names = list(set(kwargs['valves']))
        self.flashtanks.names = list(set(kwargs['flashtanks']))
        self.compressors.names = list(set(kwargs['compressors']))
        self.controllers.names = list(set(kwargs['controllers']))
        self.heat_exchangers.names = list(set(kwargs['heat_exchangers']))
        self.material_streams.names = list(set(kwargs['material_streams']).union(set(kwargs['material_streams_phase'])))
        self.material_streams.collected_phases = list(set(kwargs['material_streams_phase']))
        self.heaters.names = list(set(kwargs['heaters']))
        self.coolers.names = list(set(kwargs['coolers']))
        self.pipes.names = list(set(kwargs['pipes']))

        self.spreadsheets.cells = kwargs['spreadsheets']

    def build_objects(self, subFlowsheet=[]):

        main_pfd = self.case.Flowsheet
        flowsheet_operations = main_pfd.Operations

        subflowsheet_operations = []
        subflowsheet_streams = []
        for subFlowsheet_name in subFlowsheet:
            subflowsheet_operations.append(main_pfd.Flowsheets.Item(subFlowsheet_name).Operations)
            subflowsheet_streams.append(main_pfd.Flowsheets.Item(subFlowsheet_name).Streams)


        # Other Operations
        for operation in self.operations:
            operation._build_object(operation.names, flowsheet_operations, subflowsheet_operations)

        #Spreadsheets
        self.spreadsheets._build_object(self.spreadsheets.cells, flowsheet_operations, subflowsheet_operations)
        
        self.material_streams._build_object(self.material_streams.names, main_pfd.Streams, subflowsheet_streams)
        
        # if self._continue_simulation:
        #     self._load_dataframes()
        # else:
        self._build_database()
     
    

    def _build_database(self):
        time = 0.0
        # Operations
        for operation in self.operations:
            operation._build_data(time)

        # Spreadsheets
        self.spreadsheets._build_data(time)

        # Streams
        self.material_streams._build_data(time)


    def update(self, sample_time=None, time_unit=None, id=None):

        if sample_time is not None:
            # Simulando um passo de integração
            self.integrador.RunFor(sample_time, time_unit)
            # Salvando as variáveis
            t_sim = self.integrador.CurrentTime.GetValue(time_unit)
        elif id is not None:
            t_sim = id
        else:
            t_sim = ""
        
        for operation in self.operations:
            operation._update_data(time = t_sim)
        
        self.material_streams._update_data(time = t_sim)

        self.spreadsheets._update_data(time = t_sim)



    def exporting_units(self, operations):
        with open(path.join(self.OUTPUT_FOLDER,'_simulation_properties.txt'), 'w') as outfile:
            for operation in operations:
                if operation._operation_title != 'materialstream':
                    outfile.write(f"{operation._operation_title} properties:\n" )
                    outfile.writelines([f' {prop}: {operation.properties[prop]}\n' for prop in operation.properties])
                    outfile.write(f"\n")

                else:
                    material_stream_properties = dict(main_properties = self.material_streams.properties, 
                                                      phases_properties = self.material_streams._phase_properties,
                                                      components_properties = self.material_streams._components_properties)
                    outfile.write(f"{operation._operation_title} properties:\n")
                    for type, prop_dict in material_stream_properties.items():
                        outfile.write(f" {type}\n")
                        for prop, unit in prop_dict.items():
                            outfile.writelines(f"  {prop}: {unit}\n")
                        outfile.write(f"\n")
                

    def finish(self, quit_unisim=True, save_simulation=None, export_csv=False):
        """
        Finish the simulation, exports units, optionally closes UniSim, and optionally saves simulation results to a csv file.
        """
        if save_simulation is None:
            save_simulation = True if self._continue_simulation else False

        # Save summary
        summary_filename = '_simulation_summary.txt'
        try:
            with open(path.join(self.OUTPUT_FOLDER, summary_filename), 'w') as f:
                f.write(f'file:{self._simulation_name}\n')
                f.write(f'material_streams:{list(self.material_streams.objects.keys())}\n')
                f.write(f'pumps:{list(self.pumps.objects.keys())}\n')
                f.write(f'valves:{list(self.valves.objects.keys())}\n')
                f.write(f'compressors:{list(self.compressors.objects.keys())}\n')
                f.write(f'controllers:{list(self.controllers.objects.keys())}\n')
                f.write(f'heat_exchangers:{list(self.heat_exchangers.objects.keys())}\n')
                f.write(f'heaters:{list(self.heaters.objects.keys())}\n')
                f.write(f'coolers:{list(self.coolers.objects.keys())}\n')
                f.write(f'flashtanks:{list(self.flashtanks.objects.keys())}\n')
                f.write(f"pipesegs:{list(self.pipes.objects.keys())}\n")
                f.write(f"spreadsheets:{self.spreadsheets.names}")
        except Exception as e:
            print(f"Could not save summary file {summary_filename}: {str(e)}")
            traceback.print_exc()

        # exporting units
        try:
            SimulationConnector.exporting_units(self, self.operations)
        except Exception as e:
            print(f"Error exporting units: {e}")
            traceback.print_exc()

        # export data in csv files
        if export_csv:
            try:
                for operation in self.operations:
                    operation._save_to_csv(self.OUTPUT_FOLDER)

                self.material_streams._save_to_csv(self.OUTPUT_FOLDER)

            except Exception as e:
                print(f"Error saving dataframes: {e}")
                traceback.print_exc()

        self.db_conn.close()

        if quit_unisim:
            if not self._simulation_abort:
                self.case.Close(save_simulation)
                self.unisim.Quit() # Fecha o unisim
            else:
                
                system("taskkill /f /im unisimdesign.exe")
    
    # Custom database features
    
    def create_table(self, table_name, columns, primary_keys=None):
        """
        Create a custom table with specified columns.
        
        Args:
            table_name: Name of the table to create
            columns: List of column definitions (e.g., ["name TEXT", "value REAL", "timestamp INTEGER"])
            primary_keys: List of column names to use as composite primary key (optional)
        """
        if primary_keys:
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {', '.join(columns)},
                PRIMARY KEY ({', '.join(primary_keys)})
            )
            """
        else:
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {', '.join(columns)}
            )
            """
        
        self.cursor.execute(create_sql)
        self.db_conn.commit()
        print(f"Table '{table_name}' created successfully")
    
    def add_columns(self, table_name, columns):
        """
        Add new columns to an existing table.
        
        Args:
            table_name: Name of the table to modify
            columns: List of column definitions (e.g., ["new_col1 REAL", "new_col2 TEXT"])
        """
        # Get existing columns
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = [row[1] for row in self.cursor.fetchall()]
        
        for column_def in columns:
            column_name = column_def.split()[0]  # Extract column name from definition
            if column_name not in existing_columns:
                add_column = f"ALTER TABLE {table_name} ADD COLUMN {column_def}"
                self.cursor.execute(add_column)
                print(f"New column '{column_name}' added to {table_name}")
        
        self.db_conn.commit()
    
    def insert_row(self, table_name, data, conflict_columns=None, update_columns=None):
        """
        Insert or update rows in a custom table.
        
        Args:
            table_name: Name of the table to insert into
            data: Dictionary or list of dictionaries with column names as keys
            conflict_columns: List of columns that define uniqueness for ON CONFLICT
            update_columns: List of columns to update on conflict (if None, updates all except conflict columns)
        """
        # Convert single dict to list for uniform handling
        if isinstance(data, dict):
            data_list = [data]
        else:
            data_list = data
        
        if not data_list:
            return
        
        # Get columns from the first data item
        columns = list(data_list[0].keys())
        
        # Prepare values
        all_values = []
        for row_data in data_list:
            values = tuple(row_data[col] for col in columns)
            all_values.append(values)
        
        # Build and execute query
        placeholders = ', '.join(['?'] * len(columns))
        
        if conflict_columns:
            # Determine which columns to update
            if update_columns:
                update_set = ', '.join([f"{col}=excluded.{col}" for col in update_columns])
            else:
                # Update all columns except the conflict columns
                update_cols = [col for col in columns if col not in conflict_columns]
                update_set = ', '.join([f"{col}=excluded.{col}" for col in update_cols])
            
            query = f"""
                INSERT INTO {table_name} ({', '.join(columns)}) 
                VALUES ({placeholders})
                ON CONFLICT({', '.join(conflict_columns)}) DO UPDATE SET 
                {update_set}
            """
        else:
            query = f"""
                INSERT INTO {table_name} ({', '.join(columns)}) 
                VALUES ({placeholders})
            """
        
        self.cursor.executemany(query, all_values)
        self.db_conn.commit()
        print(f"Inserted/updated {len(all_values)} rows in {table_name}")
    
    def update_row(self, table_name, data, condition_columns):
        """
        Update existing rows based on condition.
        
        Args:
            table_name: Name of the table to update
            data: Dictionary with column names and new values
            condition_columns: List of columns to use in WHERE clause
        """
        # Build SET clause
        set_clause = ', '.join([f"{col} = ?" for col in data.keys() if col not in condition_columns])
        
        # Build WHERE clause
        where_clause = ' AND '.join([f"{col} = ?" for col in condition_columns])
        
        # Prepare values
        set_values = [data[col] for col in data.keys() if col not in condition_columns]
        condition_values = [data[col] for col in condition_columns]
        all_values = set_values + condition_values
        
        query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"
        self.cursor.execute(query, all_values)
        self.db_conn.commit()
        print(f"Updated rows in {table_name}")
    
    def query_table(self, table_name, conditions=None, order_by=None, limit=None):
        """
        Query data from a custom table.
        
        Args:
            table_name: Name of the table to query
            conditions: Dictionary of conditions (e.g., {"name": "value", "time >": 100})
            order_by: Column to order by (optional)
            limit: Maximum number of rows to return (optional)
        """
        query = f"SELECT * FROM {table_name}"
        
        if conditions:
            where_clauses = []
            values = []
            for key, value in conditions.items():
                if " " in key:  # Handles operators like "time >", "name LIKE"
                    where_clauses.append(f"{key} ?")
                else:
                    where_clauses.append(f"{key} = ?")
                values.append(value)
            
            query += " WHERE " + " AND ".join(where_clauses)
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        self.cursor.execute(query, values if conditions else [])
        return self.cursor.fetchall()
    
    def get_table_info(self, table_name):
        """Get information about table columns."""
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        return self.cursor.fetchall()
    
    #####################################


    # UnisimConnect user functions

    def _get_operations_by_type(self, operation_type):
        """Helper method to get operations by type"""
        return [name for name in self.case.Flowsheet.Operations.Names
                if self.case.Flowsheet.Operations[name].TypeName == operation_type]

    def get_pumps(self):
        """Returns list of all pump names in the simulation"""
        return self._get_operations_by_type("pumpop")

    def get_heatexchangers(self):
        """Returns list of all heat exchanger names in the simulation"""
        return self._get_operations_by_type("heatexop")

    def get_valves(self):
        """Returns list of all valve names in the simulation"""
        return self._get_operations_by_type("valveop")

    def get_flashtanks(self):
        """Returns list of all flash tank names in the simulation"""
        return self._get_operations_by_type("flashtank")

    def get_controllers(self):
        """Returns list of all controller names in the simulation"""
        return self._get_operations_by_type("fbcontrolop")

    def get_compressors(self):
        """Returns list of all compressor names in the simulation"""
        return self._get_operations_by_type("compressor")

    def get_material_streams(self):
        """Returns list of all material stream names in the simulation"""
        return sorted(list(self.case.Flowsheet.MaterialStreams.Names))

    def get_spreadsheets(self):
        return self._get_operations_by_type("spreadsheetop")

    def get_subflowsheets(self) -> list[tuple]:
        """
        Returns list of (Name, TaggedName) tuples for all subflowsheets
        """
        subflowsheets = self.case.Flowsheet.Flowsheets
        return [
            (name, subflowsheets.Item(name).TaggedName)
            for name in sorted(subflowsheets.Names)
        ]

    def get_all_operations(self):
        """Returns dictionary of all element types with their names"""
        operations_by_type = {}
        for name in self.case.Flowsheet.Operations.Names:
            operation_type = self.case.Flowsheet.Operations[name].TypeName
            if operation_type not in operations_by_type:
                operations_by_type[operation_type] = []

            # Then append the name to that list
            operations_by_type[operation_type].append(name)
        
        return operations_by_type